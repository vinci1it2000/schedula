import {withTheme} from './components/Form';
import {HoxRoot} from "hox";
import {useEffect, useState, createRef} from 'react'
import defineValidator from "./components/validator";
import {getUiOptions} from "@rjsf/utils";

function Form(
    {
        schema,
        csrf_token,
        refresh_csrf,
        uiSchema = {},
        url = '/',
        name = "form",
        removeReturnOnChange = true,
        theme,
        liveValidate = true,
        nonce,
        ...props
    }
) {
    const language = getUiOptions("uiSchema" in props ? props.uiSchema : {}).language || ("language" in props ? props.language : 'en_US')
    let [validator, setValidator] = useState(null);
    useEffect(() => {
        defineValidator(language, schema, nonce).then(setValidator);
    },[]);
    const BaseForm = withTheme(theme);
    const rootRef = createRef()
    return <HoxRoot key={name}>
        {validator?<BaseForm
            rootRef={rootRef}
            language={language}
            csrf_token={csrf_token}
            refresh_csrf={refresh_csrf}
            name={name}
            id={name}
            schema={schema}
            url={url}
            nonce={nonce}
            uiSchema={uiSchema}
            showErrorList={false}
            omitExtraData={true}
            editOnChange={null}
            preSubmit={null}
            postSubmit={null}
            showDebug={false}
            liveValidate={false}
            validator={validator}
            debounceValidate={liveValidate}
            experimental_defaultFormStateBehavior={{
                arrayMinItems: 'populate',
                emptyObjectFields: 'populateAllDefaults'
            }}
            {...props}
        />: <div>loading...</div>}
    </HoxRoot>
}

export {Form as default};

