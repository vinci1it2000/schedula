import {withTheme} from './components/Form';
import {HoxRoot} from "hox";
import React, {useMemo} from 'react'
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
        ...props
    }
) {
    const language = getUiOptions("uiSchema" in props ? props.uiSchema : {}).language || ("language" in props ? props.language : 'en_US')
    const validator = useMemo(() => {
        return defineValidator(language)
    }, [language])
    const BaseForm = withTheme(theme);
    const rootRef = React.createRef()
    return <HoxRoot key={name}>
        <BaseForm
            rootRef={rootRef}
            language="en_US"
            csrf_token={csrf_token}
            refresh_csrf={refresh_csrf}
            name={name}
            id={name}
            schema={schema}
            url={url}
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
        />
    </HoxRoot>
}

export {Form as default};

