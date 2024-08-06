import {withTheme} from './components/Form';
import {HoxRoot} from "hox";
import {useEffect, useState, createRef, useMemo} from 'react'
import defineValidator from "./components/validator";
import {getUiOptions} from "@rjsf/utils";
import i18n, {translateJSON} from './components/translator'

function Form(
    {
        schema: rootSchema,
        csrf_token,
        refresh_csrf,
        uiSchema: rootUiSchema = {},
        url = '/',
        name = "form",
        removeReturnOnChange = true,
        theme,
        liveValidate = true,
        nonce,
        language: _language = 'en_US',
        precompiledValidator: _precompiledValidator = true,
        formContext,
        ...props
    }
) {
    const {
        language = _language,
        precompiledValidator = _precompiledValidator,
        formContext: optionsFormContext,
        ...optionsProps
    } = getUiOptions(rootUiSchema).props || {}

    let [futureProps, setFutureProps] = useState(null);
    useEffect(() => {
        i18n.changeLanguage(language, (err, t) => {
            console.log(err)
            const schema = translateJSON(t, rootSchema)
            defineValidator(precompiledValidator, language, schema, nonce).then(validator => {
                const uiSchema = translateJSON(t, rootUiSchema)
                setFutureProps({schema, uiSchema, validator})
            })
        })
    }, []);
    const BaseForm = useMemo(() => (withTheme(theme)), [theme]);
    const rootRef = createRef()
    return <HoxRoot key={name}>
        {futureProps ? <BaseForm
            rootRef={rootRef}
            language={language}
            csrf_token={csrf_token}
            refresh_csrf={refresh_csrf}
            name={name}
            id={name}
            idPrefix={name}
            idSeparator={'.'}
            rootSchema={rootSchema}
            rootUiSchema={rootUiSchema}
            url={url}
            nonce={nonce}
            showErrorList={false}
            omitExtraData={true}
            editOnChange={null}
            preSubmit={null}
            postSubmit={null}
            showDebug={false}
            liveValidate={false}
            precompiledValidator={precompiledValidator}
            debounceValidate={liveValidate}
            experimental_defaultFormStateBehavior={{
                arrayMinItems: {populate: 'all'},
                emptyObjectFields: 'populateAllDefaults',
                allOf: 'populateDefaults',
            }}
            formContext={{...formContext, ...optionsFormContext}}
            {...futureProps}
            {...props}
            {...optionsProps}
        /> : <div>loading...</div>}
    </HoxRoot>
}

export {Form as default};

