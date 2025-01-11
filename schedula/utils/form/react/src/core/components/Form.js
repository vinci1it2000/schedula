import React, {forwardRef} from "react"
import {
    createSchemaUtils,
    deepEquals,
    getTemplate,
    mergeObjects,
    toErrorList,
    getUiOptions,
    isObject,
    validationDataMerge,
    UI_GLOBAL_OPTIONS_KEY
} from "@rjsf/utils"
import _ from "lodash"
import get from "lodash/get";
import cloneDeep from "lodash/cloneDeep";
import isEqual from "lodash/isEqual"
import debounce from "lodash/debounce";
import postData from "../utils/fetch";
import defineValidator from "./validator";
import i18n, {translateJSON} from "./translator";
import patchSchemaUtils from './patchSchemaUtils'
import BaseForm from "@rjsf/core"
import isEmpty from "lodash/isEmpty";
import EventEmitter from "events"

function customCreateSchemaUtils(validator, schema, experimental_defaultFormStateBehavior, experimental_customMergeAllOf) {
    return patchSchemaUtils(createSchemaUtils(validator, schema, experimental_defaultFormStateBehavior, experimental_customMergeAllOf))
}

/** The `Form` component renders the outer form and all the fields defined in the `schema` */
export default class Form extends BaseForm {
    constructor(props) {
        super(props);
        this.state.FormContext = React.createContext({form: this})
        this.state.emitter = new EventEmitter()
        this.state["schemaUtils"] = customCreateSchemaUtils(
            props.validator,
            props.schema,
            props.experimental_defaultFormStateBehavior,
            props.experimental_customMergeAllOf
        )
    }

    componentDidMount() {
        this.editOnChange(this.state.formData)
        this.debounceValidate(this.props.onLoad)
    }

    compileFunc(func) {
        let locals = this.props.uiFunctions || {}, keys;
        if (typeof func !== 'string') {
            let {func: _func, locals: _locals = {}} = func;
            locals = {...locals, ..._locals}
            func = _func
        }
        keys = Object.keys(locals)
        return new Function('form', "_", ...keys, "return " + func)(this, _, ...keys.map(k => locals[k]))
    }

    t(object, options, t) {
        return translateJSON(t || i18n.t, object, options)
    }

    n(number, options) {
        let {scale = 1, ...opt} = options || {}
        return new Intl.NumberFormat(this.state.language.replace('_', '-'), {
            minimumFractionDigits: 0, maximumFractionDigits: 20, ...opt
        }).format(number * scale);
    }

    d(date, options) {
        if (typeof date === 'string') {
            if (date === 'now') {
                date = new Date()
            } else {
                date = new Date(date)
            }
        }
        return new Intl.DateTimeFormat(this.state.language.replace('_', '-'), options).format(date);
    }

    updateLanguage(language, callback) {
        this.postData({
            url: '/locales/' + language
        }, ({data: {language}}) => {
            this.setState({
                ...this.state, loading: true
            }, () => {
                i18n.changeLanguage(language, (err, t) => {
                    console.log(err)
                    const schema = this.t(this.state.rootSchema)
                    defineValidator(this.props.precompiledValidator, language, schema, this.props.nonce).then(validator => {
                        const uiSchema = this.t(this.state.rootUiSchema)
                        const experimental_defaultFormStateBehavior = this.props.experimental_defaultFormStateBehavior
                        const experimental_customMergeAllOf = this.props.experimental_customMergeAllOf
                        this.setState({
                            ...this.state,
                            loading: false,
                            language,
                            schema,
                            uiSchema,
                            schemaUtils: customCreateSchemaUtils(validator, schema, experimental_defaultFormStateBehavior, experimental_customMergeAllOf)
                        }, () => {
                            if (callback) {
                                callback(this)
                            }
                            this.validateForm()
                        })
                    })
                })
            })
        })
    }

    /** Extracts the updated state from the given `props` and `inputFormData`. As part of this process, the
     * `inputFormData` is first processed to add any missing required defaults. After that, the data is run through the
     * validation process IF required by the `props`.
     *
     * @param props - The props passed to the `Form`
     * @param inputFormData - The new or current data for the `Form`
     * @param retrievedSchema - An expanded schema, if not provided, it will be retrieved from the `schema` and `formData`.
     * @param isSchemaChanged - A flag indicating whether the schema has changed.
     * @param formDataChangedFields - The changed fields of `formData`
     * @returns - The new state for the `Form`
     */
    getStateFromProps(
        props,
        inputFormData,
        retrievedSchema,
        isSchemaChanged = false,
        formDataChangedFields = []
    ) {
        const state = this.state || {}
        const schema = "schema" in props ? props.schema : this.props.schema
        const uiSchema =
            ("uiSchema" in props ? props.uiSchema : this.props.uiSchema) || {}
        const edit = typeof inputFormData !== "undefined"
        const liveValidate =
            "liveValidate" in props ? props.liveValidate : this.props.liveValidate
        const mustValidate = edit && !props.noValidate && liveValidate
        const rootSchema = schema
        const experimental_defaultFormStateBehavior =
            "experimental_defaultFormStateBehavior" in props
                ? props.experimental_defaultFormStateBehavior
                : this.props.experimental_defaultFormStateBehavior
        const experimental_customMergeAllOf =
            "experimental_customMergeAllOf" in props
                ? props.experimental_customMergeAllOf
                : this.props.experimental_customMergeAllOf
        let schemaUtils = state.schemaUtils
        if (
            !schemaUtils ||
            schemaUtils.doesSchemaUtilsDiffer(
                props.validator,
                rootSchema,
                experimental_defaultFormStateBehavior,
                experimental_customMergeAllOf
            )
        ) {
            schemaUtils = customCreateSchemaUtils(
                props.validator,
                rootSchema,
                experimental_defaultFormStateBehavior,
                experimental_customMergeAllOf
            )
        }
        const formData = schemaUtils.getDefaultFormState(schema, inputFormData)
        const _retrievedSchema = this.updateRetrievedSchema(
            retrievedSchema ?? schemaUtils.retrieveSchema(schema, formData)
        )

        const getCurrentErrors = () => {
            // If the `props.noValidate` option is set or the schema has changed, we reset the error state.
            if (props.noValidate || isSchemaChanged) {
                return {errors: [], errorSchema: {}}
            } else if (!props.liveValidate) {
                return {
                    errors: state.schemaValidationErrors || [],
                    errorSchema: state.schemaValidationErrorSchema || {}
                }
            }
            return {
                errors: state.errors || [],
                errorSchema: state.errorSchema || {}
            }
        }

        let errors
        let errorSchema
        let schemaValidationErrors = state.schemaValidationErrors
        let schemaValidationErrorSchema = state.schemaValidationErrorSchema
        if (mustValidate) {
            const schemaValidation = this.validate(
                formData,
                schema,
                schemaUtils,
                _retrievedSchema
            )
            errors = schemaValidation.errors
            // If retrievedSchema is undefined which means the schema or formData has changed, we do not merge state.
            // Else in the case where it hasn't changed, we merge 'state.errorSchema' with 'schemaValidation.errorSchema.' This done to display the raised field error.
            if (retrievedSchema === undefined) {
                errorSchema = schemaValidation.errorSchema
            } else {
                errorSchema = mergeObjects(
                    this.state?.errorSchema,
                    schemaValidation.errorSchema,
                    "preventDuplicates"
                )
            }
            schemaValidationErrors = errors
            schemaValidationErrorSchema = errorSchema
        } else {
            const currentErrors = getCurrentErrors()
            errors = currentErrors.errors
            errorSchema = currentErrors.errorSchema
            if (formDataChangedFields.length > 0) {
                const newErrorSchema = formDataChangedFields.reduce((acc, key) => {
                    acc[key] = undefined
                    return acc
                }, {})
                errorSchema = schemaValidationErrorSchema = mergeObjects(
                    currentErrors.errorSchema,
                    newErrorSchema,
                    "preventDuplicates"
                )
            }
        }

        if (props.extraErrors) {
            const merged = validationDataMerge(
                {errorSchema, errors},
                props.extraErrors
            )
            errorSchema = merged.errorSchema
            errors = merged.errors
        }
        const idSchema = schemaUtils.toIdSchema(
            _retrievedSchema,
            uiSchema["ui:rootFieldId"],
            formData,
            props.idPrefix,
            props.idSeparator
        )
        const nextState = {
            schemaUtils,
            schema,
            uiSchema,
            idSchema,
            formData,
            edit,
            errors,
            errorSchema,
            schemaValidationErrors,
            schemaValidationErrorSchema,
            retrievedSchema: _retrievedSchema
        }

        const _rootSchema = get(props, "rootSchema", this.props.schema)
        const rootUiSchema = get(props, "rootUiSchema", this.props.uiSchema) || {}
        const language = get(props, "language", this.props.language) || 'en_US'
        const csrf_token = "csrf_token" in state ? state.csrf_token : ("csrf_token" in props ? props.csrf_token : this.props.csrf_token)
        const submitCount = "submitCount" in state ? state.submitCount : 0
        const {formContext = {}} = props
        const userInfo = "userInfo" in state ? state.userInfo : ("userInfo" in formContext ? formContext.userInfo : this.props.userInfo) || {}
        const runnable = "runnable" in state ? state.runnable : ("runnable" in formContext ? formContext.runnable : true)
        const debuggable = "debuggable" in state ? state.debuggable : ("debuggable" in formContext ? formContext.debuggable : true)
        const loading = "loading" in state ? state.loading : false
        const debugUrl = "debugUrl" in state ? state.debugUrl : ""
        return {
            ...nextState,
            rootSchema: _rootSchema,
            rootUiSchema,
            csrf_token,
            loading,
            runnable,
            debuggable,
            debugUrl,
            userInfo,
            submitCount,
            language
        }
    }

    /** Validates the `formData` against the `schema` using the `altSchemaUtils` (if provided otherwise it uses the
     * `schemaUtils` in the state), returning the results.
     *
     * @param formData - The new form data to validate
     * @param schema - The schema used to validate against
     * @param altSchemaUtils - The alternate schemaUtils to use for validation
     */
    validate(
        formData,
        schema = this.props.schema,
        altSchemaUtils,
        retrievedSchema
    ) {
        const schemaUtils = altSchemaUtils ? altSchemaUtils : this.state.schemaUtils
        schema = schema ? schema : this.state.schema
        const uiSchema = this.state ? this.state.uiSchema : this.props.uiSchema
        const {customValidate, transformErrors} = this.props
        const resolvedSchema =
            retrievedSchema ?? schemaUtils.retrieveSchema(schema, formData)
        return schemaUtils
            .getValidator()
            .validateFormData(
                formData,
                resolvedSchema,
                customValidate,
                transformErrors,
                uiSchema
            )
    }

    debounceValidate = debounce((callback) => {
        if (!this.props.noValidate && this.validateForm() && ((this.state.schemaValidationErrors || []).length || (this.state.errors || []).length)) {
            this.setState({
                ...this.state,
                errors: [],
                errorSchema: {},
                schemaValidationErrorSchema: {},
                schemaValidationErrors: []
            })
        }
        if (callback) callback(this)
    }, 50)

    editOnChange(formData, id) {
        if (this.props.editOnChange) {
            const {editOnChange, ...props} = this.props
            return editOnChange({
                ...props,
                formData: cloneDeep(formData),
                _,
                form: this
            }, id);
        }
        return formData
    }

    postSubmit({data, input, formData}) {
        if (this.props.postSubmit) {
            const {postSubmit, ...props} = this.props
            data = postSubmit({...props, data, input, formData, _, form: this});
        }
        return {data}
    }

    preSubmit({input, formData}) {
        if (this.props.preSubmit) {
            const {preSubmit, ...props} = this.props
            return preSubmit({...props, input, formData, _, form: this});
        }
        return input
    }

    debounceOnChange = debounce((formData, newErrorSchema, id) => {
        const {
            extraErrors,
            omitExtraData,
            liveOmit,
            noValidate,
            liveValidate,
            debounceValidate,
            onChange
        } = this.props
        const {schemaUtils, schema, retrievedSchema} = this.state;
        if (isObject(formData) || Array.isArray(formData)) {
            const newState = this.getStateFromProps(this.props, formData, retrievedSchema)
            formData = newState.formData
        }
        formData = this.editOnChange(formData, id)
        const mustValidate = !noValidate && liveValidate

        let state = {formData, schema, debugUrl: ""}

        let newFormData = formData, _retrievedSchema;
        if (omitExtraData === true && liveOmit === true) {
            _retrievedSchema = schemaUtils.retrieveSchema(schema, formData)
            const pathSchema = schemaUtils.toPathSchema(retrievedSchema, "", formData)
            const fieldNames = this.getFieldNames(pathSchema, formData)

            newFormData = this.getUsedFormData(formData, fieldNames)
            state = {
                ...state,
                formData: newFormData
            }
        }

        if (mustValidate) {
            const schemaValidation = this.validate(
                newFormData,
                schema,
                schemaUtils,
                retrievedSchema
            )
            let errors = schemaValidation.errors
            let errorSchema = schemaValidation.errorSchema
            const schemaValidationErrors = errors
            const schemaValidationErrorSchema = errorSchema
            if (extraErrors) {
                const merged = validationDataMerge(schemaValidation, extraErrors)
                errorSchema = merged.errorSchema
                errors = merged.errors
            }
            // Merging 'newErrorSchema' into 'errorSchema' to display the custom raised errors.
            if (newErrorSchema) {
                const filteredErrors = this.filterErrorsBasedOnSchema(
                    newErrorSchema,
                    retrievedSchema,
                    newFormData
                )
                errorSchema = mergeObjects(
                    errorSchema,
                    filteredErrors,
                    "preventDuplicates"
                )
            }
            state = {
                ...state,
                formData: newFormData,
                errors,
                errorSchema,
                schemaValidationErrors,
                schemaValidationErrorSchema
            }
        } else if (!noValidate && newErrorSchema) {
            const errorSchema = extraErrors ? mergeObjects(newErrorSchema, extraErrors, "preventDuplicates") : newErrorSchema

            const {errors: prevErrors} = this.state
            const errors = toErrorList(errorSchema)
            if (isEqual(prevErrors, errors)) {
                state = {...state, errorSchema, errors}
            }

        }
        const runnable = this.state.runnable || !deepEquals(this.state.formData, state.formData)
        state = {
            ...state,
            runnable: runnable,
            debuggable: runnable || this.state.debuggable || !state.debugUrl,
        }
        if (_retrievedSchema) {
            state.retrievedSchema = _retrievedSchema;
        }
        this.setState(state, () => {
            onChange && onChange({...this.state, ...state}, id)
            debounceValidate && this.debounceValidate()
        })
    }, 50)

    /** Function to handle changes made to a field in the `Form`. This handler receives an entirely new copy of the
     * `formData` along with a new `ErrorSchema`. It will first update the `formData` with any missing default fields and
     * then, if `omitExtraData` and `liveOmit` are turned on, the `formData` will be filterer to remove any extra data not
     * in a form field. Then, the resulting formData will be validated if required. The state will be updated with the new
     * updated (potentially filtered) `formData`, any errors that resulted from validation. Finally the `onChange`
     * callback will be called if specified with the updated state.
     *
     * @param formData - The new form data from a change to a field
     * @param newErrorSchema - The new `ErrorSchema` based on the field change
     * @param id - The id of the field that caused the change
     */
    onChange = (formData, newErrorSchema, id) => {
        this.debounceOnChange(formData, newErrorSchema, id)
    }

    debounceSubmit = debounce((event, detail) => {
        const {
            omitExtraData, extraErrors, noValidate, onSubmit
        } = this.props
        let {formData: newFormData} = this.state
        const {schema, schemaUtils} = this.state

        if (omitExtraData === true) {
            const retrievedSchema = schemaUtils.retrieveSchema(schema, newFormData);
            const pathSchema = schemaUtils.toPathSchema(retrievedSchema, '', newFormData);

            const fieldNames = this.getFieldNames(pathSchema, newFormData);

            newFormData = this.getUsedFormData(newFormData, fieldNames);
        }
        newFormData = this.editOnChange(newFormData)

        if (noValidate || this.validateFormWithFormData(newFormData)) {
            // There are no errors generated through schema validation.
            // Check for user provided errors and update state accordingly.
            const errorSchema = extraErrors || {}
            const errors = extraErrors ? toErrorList(extraErrors) : []
            const {input = {}} = newFormData

            const data = this.preSubmit({
                input, formData: newFormData
            });
            let state = {
                formData: newFormData,
                errors,
                errorSchema,
                schemaValidationErrors: [],
                schemaValidationErrorSchema: {},
                debugUrl: ""
            }
            let newState = {
                loading: false, submitCount: this.state.submitCount + 1
            }

            this.setState(state, () => {
                this.postData({data, ...detail}, (
                    {
                        data: postData,
                        debugUrl,
                        state: fetchState
                    }) => {
                    const {data} = this.postSubmit({
                        data: postData, input, formData: newFormData
                    })
                    if (debugUrl) {
                        newState = {...newState, debugUrl}
                    }
                    if (!data.hasOwnProperty('error')) {
                        newState = {
                            ...newState,
                            formData: {input, ...data},
                            runnable: false,
                            debuggable: !newState.debugUrl
                        }
                    }
                    newState = {...newState, ...fetchState}
                    this.setState({...this.state, ...state, ...newState}, () => {
                        if (data.hasOwnProperty('error')) {
                            this.props.notify({message: data.error})
                        } else {
                            if (onSubmit) {
                                onSubmit({
                                    ...this.state, status: "submitted"
                                }, event)
                            }
                        }
                        this.validateForm()
                    })
                }, () => {
                    this.setState({
                        ...this.state, ...state, ...newState
                    })
                });
            })
        } else {
            this.setState({...this.state, loading: false})
        }
    }, 50)

    flashMessages = (messages) => {
        if (this.props.notify) (messages || []).forEach(([type, message]) => {
            this.props.notify({type, message})
        })
    }
    postData = (kwargs, onSuccess, onError, notify = true) => {
        return postData({
            url: this.props.url || '/',
            form: this,
            method: 'POST',
            headers: {}, ...kwargs
        }).then(({data, debugUrl}) => {
            this.flashMessages(data.messages)
            return {debugUrl, data}
        }).then((response) => {
            let {data: {error, errors = []}} = response
            if (!isEmpty(error) || errors.length) {
                let message = (errors.length ? errors : [error]).join('\n')
                throw {...response, message}
            } else if (onSuccess) {
                onSuccess(response)
            } else {
                return response
            }
        }).catch((error = {}) => {
            if (notify) this.props.notify({
                message: this.t('Ops... something went wrong!'),
                description: error.message,
            })
            if (onError) onError(error)
        })
    }

    /** Callback function to handle when the form is submitted. First, it prevents the default event behavior. Nothing
     * happens if the target and currentTarget of the event are not the same. It will omit any extra data in the
     * `formData` in the state if `omitExtraData` is true. It will validate the resulting `formData`, reporting errors
     * via the `onError()` callback unless validation is disabled. Finally it will add in any `extraErrors` and then call
     * back the `onSubmit` callback if it was provided.
     *
     * @param event - The submit HTML form event
     */
    onSubmit = (event, detail = {}) => {
        if (event) {
            event.preventDefault()
            return
        }
        this.setState({
            ...this.state,
            loading: true,
            errors: [],
            errorSchema: {},
            schemaValidationErrors: [],
            schemaValidationErrorSchema: {}
        }, () => {
            this.debounceSubmit(event, detail)
        })
    }

    /** Returns the registry for the form */
    getRegistry() {
        let registry = super.getRegistry()
        const {uiSchema, schema, FormContext} = this.state
        registry.formContext.form = this
        registry.formContext.FormContext = FormContext
        registry.rootSchema = schema
        registry.globalUiOptions = uiSchema[UI_GLOBAL_OPTIONS_KEY]
        return registry
    }

    /**
     * If the retrievedSchema has changed the new retrievedSchema is returned.
     * Otherwise, the old retrievedSchema is returned to persist reference.
     * -  This ensures that AJV retrieves the schema from the cache when it has not changed,
     *    avoiding the performance cost of recompiling the schema.
     *
     * @param retrievedSchema The new retrieved schema.
     * @returns The new retrieved schema if it has changed, else the old retrieved schema.
     */
    updateRetrievedSchema(retrievedSchema) {
        const isTheSame = deepEquals(retrievedSchema, this.state?.retrievedSchema)
        return isTheSame ? this.state.retrievedSchema : retrievedSchema
    }

    /** Validates the form using the given `formData`. For use on form submission or on programmatic validation.
     * If `onError` is provided, then it will be called with the list of errors.
     *
     * @param formData - The form data to validate
     * @returns - True if the form is valid, false otherwise.
     */
    validateFormWithFormData = formData => {
        const {
            extraErrors,
            extraErrorsBlockSubmit,
            focusOnFirstError,
            onError
        } = this.props
        const {errors: prevErrors} = this.state
        const schemaValidation = this.validate(formData)
        let errors = schemaValidation.errors
        let errorSchema = schemaValidation.errorSchema
        const schemaValidationErrors = errors
        const schemaValidationErrorSchema = errorSchema
        const hasError =
            errors.length > 0 || (extraErrors && extraErrorsBlockSubmit)
        if (hasError) {
            if (extraErrors) {
                const merged = validationDataMerge(schemaValidation, extraErrors)
                errorSchema = merged.errorSchema
                errors = merged.errors
            }
            if (focusOnFirstError) {
                if (typeof focusOnFirstError === "function") {
                    focusOnFirstError(errors[0])
                } else {
                    this.focusOnError(errors[0])
                }
            }
            if (!isEqual(errors, prevErrors)) {
                this.setState({
                    errors: [],
                    errorSchema: {},
                    schemaValidationErrors: [],
                    schemaValidationErrorSchema: {}
                }, () => {
                    this.setState({
                        errors,
                        errorSchema,
                        schemaValidationErrors,
                        schemaValidationErrorSchema
                    }, () => {
                        if (onError) {
                            onError(errors)
                        }
                    })
                })
            }
        } else if (prevErrors.length > 0) {
            this.setState({
                errors: [],
                errorSchema: {},
                schemaValidationErrors: [],
                schemaValidationErrorSchema: {}
            })
        }
        return !hasError
    }

    /** Renders the `Form` fields inside the <form> | `tagName` or `_internalFormWrapper`, rendering any errors if
     * needed along with the submit button or any children of the form.
     */
    render() {
        const {
            children,
            id,
            idPrefix,
            idSeparator,
            className = "",
            tagName,
            name,
            method,
            target,
            action,
            autoComplete,
            enctype,
            acceptcharset,
            noHtml5Validate = false,
            disabled = false,
            readonly = false,
            showErrorList = "top",
            _internalFormWrapper,
            showDebug = false
        } = this.props;
        const {
            schema, uiSchema, formData, errorSchema, idSchema
        } = this.state;
        const registry = this.getRegistry();
        const {SchemaField} = registry.fields;
        const as = _internalFormWrapper ? tagName : undefined;
        const FormTag = _internalFormWrapper || tagName || "form";
        const uiOptions = getUiOptions(uiSchema)
        const {
            configProvider: propsConfigProvider = {},
            contentProvider: propsContentProvider = {}
        } = uiOptions
        const Loader = getTemplate('Loader', registry, uiOptions);
        const ModalProvider = getTemplate('ModalProvider', registry, uiOptions);
        const ConfigProvider = getTemplate('ConfigProvider', registry, uiOptions);
        const ContentProvider = getTemplate('ContentProvider', registry, uiOptions);
        const Debug = getTemplate('Debug', registry, uiOptions);
        const {formContext} = registry
        const {FormContext} = formContext
        return <FormContext.Provider
            value={{
                form: this, state: this.state, setState: this.setState
            }}>
            <FormTag
                className={className ? className : "rjsf"}
                id={id}
                name={name}
                method={method}
                target={target}
                action={action}
                autoComplete={autoComplete}
                encType={enctype}
                acceptCharset={acceptcharset}
                noValidate={noHtml5Validate}
                onSubmit={this.onSubmit}
                as={as}
                style={{height: '100%'}}
                ref={this.formElement}>
                <ConfigProvider {...{
                    ...propsConfigProvider, form: this
                }}>
                    <ContentProvider {...propsContentProvider}>
                        <Loader loading={this.state.loading}>
                            <ModalProvider>
                                {showErrorList === "top" && this.renderErrors(registry)}
                                <SchemaField
                                    name=""
                                    schema={schema}
                                    uiSchema={uiSchema}
                                    errorSchema={errorSchema}
                                    idSchema={idSchema}
                                    idPrefix={idPrefix}
                                    idSeparator={idSeparator}
                                    formContext={formContext}
                                    formData={formData}
                                    onChange={this.onChange}
                                    onBlur={this.onBlur}
                                    onFocus={this.onFocus}
                                    registry={registry}
                                    disabled={disabled}
                                    readonly={readonly}
                                    submitCount={this.state.submitCount}  // used to re-render
                                />
                                {typeof children === 'function' ? children(this) : children}
                                {showDebug && this.state.debugUrl ? <Debug
                                    key={name + '-Debug'}
                                    id={name + '-Debug'}
                                    src={this.state.debugUrl}
                                    name={name}/> : null}
                                {showErrorList === "bottom" && this.renderErrors(registry)}
                            </ModalProvider>
                        </Loader>
                    </ContentProvider>
                </ConfigProvider>
            </FormTag>
        </FormContext.Provider>
    }
}


export function withTheme(themeProps) {
    return forwardRef(({fields, widgets, templates, ...directProps}, ref) => {
        fields = {...themeProps?.fields, ...fields};
        widgets = {...themeProps?.widgets, ...widgets};
        templates = {
            ...themeProps?.templates, ...templates, ButtonTemplates: {
                ...themeProps?.templates?.ButtonTemplates, ...templates?.ButtonTemplates,
            },
        };
        return <Form
            ref={ref}
            {...themeProps}
            {...directProps}
            fields={fields}
            widgets={widgets}
            templates={templates}
        />
    });
}