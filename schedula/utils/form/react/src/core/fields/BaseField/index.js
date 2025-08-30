import {Component} from "react"
import {
    ADDITIONAL_PROPERTY_FLAG,
    deepEquals,
    descriptionId,
    getSchemaType,
    getTemplate,
    getUiOptions,
    ID_KEY,
    mergeObjects,
    UI_OPTIONS_KEY
} from "@rjsf/utils"
import omit from "lodash/omit"
import ReactMarkdown from "react-markdown";


/** The `SchemaFieldRender` component is the work-horse of react-jsonschema-form, determining what kind of real field to
 * render based on the `schema`, `uiSchema` and all the other props. It also deals with rendering the `anyOf` and
 * `oneOf` fields.
 *
 * @param props - The `FieldProps` for this component
 */
function BaseFieldRender(props) {
    const {
        children,
        schema: _schema,
        idSchema: _idSchema,
        uiSchema,
        formData,
        errorSchema,
        idPrefix,
        idSeparator,
        name,
        onChange,
        onKeyChange,
        onDropPropertyClick,
        required,
        registry,
        wasPropertyKeyModified = false
    } = props
    const {formContext, schemaUtils, globalUiOptions} = registry
    const uiOptions = getUiOptions(uiSchema, globalUiOptions)
    const FieldTemplate = getTemplate("FieldTemplate", registry, uiOptions)
    const DescriptionFieldTemplate = getTemplate(
        "DescriptionFieldTemplate",
        registry,
        uiOptions
    )
    const FieldHelpTemplate = getTemplate(
        "FieldHelpTemplate",
        registry,
        uiOptions
    )
    const FieldErrorTemplate = getTemplate(
        "FieldErrorTemplate",
        registry,
        uiOptions
    )
    const schema = schemaUtils.retrieveSchema(_schema, formData)
    const fieldId = _idSchema[ID_KEY]
    const idSchema = mergeObjects(
        schemaUtils.toIdSchema(schema, fieldId, formData, idPrefix, idSeparator),
        _idSchema
    )

    const disabled = Boolean(props.disabled || uiOptions.disabled)
    const readonly = Boolean(
        props.readonly ||
        uiOptions.readonly ||
        props.schema.readOnly ||
        schema.readOnly
    )
    const uiSchemaHideError = uiOptions.hideError
    // Set hideError to the value provided in the uiSchema, otherwise stick with the prop to propagate to children
    const hideError =
        uiSchemaHideError === undefined
            ? props.hideError
            : Boolean(uiSchemaHideError)
    if (Object.keys(schema).length === 0) {
        return null
    }

    const {__errors} = errorSchema || {}
    // See #439: uiSchema: Don't pass consumed class names or style to child components
    const fieldUiSchema = omit(uiSchema, [
        "ui:classNames",
        "classNames",
        "ui:style"
    ])
    if (UI_OPTIONS_KEY in fieldUiSchema) {
        fieldUiSchema[UI_OPTIONS_KEY] = omit(fieldUiSchema[UI_OPTIONS_KEY], [
            "classNames",
            "style"
        ])
    }


    const id = idSchema[ID_KEY]

    // If this schema has a title defined, but the user has set a new key/label, retain their input.
    let label
    if (wasPropertyKeyModified) {
        label = name
    } else {
        label =
            ADDITIONAL_PROPERTY_FLAG in schema
                ? name
                : uiOptions.title ||
                props.schema.title ||
                schema.title ||
                props.title ||
                name
    }

    const displayLabel = !!label
    const description =
        uiOptions.description ||
        props.schema.description ||
        schema.description ||
        ""

    const richDescription = uiOptions.enableMarkdownInDescription ? (
        <ReactMarkdown
            skipHtml={true}
            components={{
                a: ({node, href, children, ...props}) => (
                    <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        {...props}
                    >
                        {children}
                    </a>
                ),
            }}
        >
            {description}
        </ReactMarkdown>
    ) : (
        description
    )

    const help = uiOptions.help
    const hidden = uiOptions.widget === "hidden"

    const classNames = ["form-group", "field", `field-${getSchemaType(schema)}`]
    if (!hideError && __errors && __errors.length > 0) {
        classNames.push("field-error has-error has-danger")
    }
    if (uiSchema?.classNames) {
        if (process.env.NODE_ENV !== "production") {
            console.warn(
                "'uiSchema.classNames' is deprecated and may be removed in a major release; Use 'ui:classNames' instead."
            )
        }
        classNames.push(uiSchema.classNames)
    }
    if (uiOptions.classNames) {
        classNames.push(uiOptions.classNames)
    }

    const helpComponent = (
        <FieldHelpTemplate
            help={help}
            idSchema={idSchema}
            schema={schema}
            uiSchema={uiSchema}
            hasErrors={!hideError && __errors && __errors.length > 0}
            registry={registry}
        />
    )
    /*
     * AnyOf/OneOf errors handled by child schema
     * unless it can be rendered as select control
     */
    const errorsComponent =
        hideError ||
        ((schema.anyOf || schema.oneOf) && (!(schemaUtils.isSelect(schema) || schema.cascader))) ? (
            undefined
        ) : (
            <FieldErrorTemplate
                errors={__errors}
                errorSchema={errorSchema}
                idSchema={idSchema}
                schema={schema}
                uiSchema={uiSchema}
                registry={registry}
            />
        )
    const fieldProps = {
        description: (
            <DescriptionFieldTemplate
                id={descriptionId(id)}
                description={richDescription}
                schema={schema}
                uiSchema={uiSchema}
                registry={registry}
            />
        ),
        rawDescription: description,
        help: helpComponent,
        rawHelp: typeof help === "string" ? help : undefined,
        errors: errorsComponent,
        rawErrors: hideError ? undefined : __errors,
        id,
        label,
        hidden,
        onChange,
        onKeyChange,
        onDropPropertyClick,
        required,
        disabled,
        readonly,
        hideError,
        displayLabel,
        classNames: classNames.join(" ").trim(),
        style: uiOptions.style,
        formContext,
        formData,
        schema,
        uiSchema,
        registry
    }


    return (
        <FieldTemplate {...fieldProps}>
            {children}
        </FieldTemplate>
    )
}

/** The `SchemaField` component determines whether it is necessary to rerender the component based on any props changes
 * and if so, calls the `SchemaFieldRender` component with the props.
 */
class BaseField extends Component {
    shouldComponentUpdate(nextProps) {
        return !deepEquals(this.props, nextProps)
    }

    render() {
        return <BaseFieldRender {...this.props} />
    }
}

export default BaseField
