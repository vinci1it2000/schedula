import {withTheme} from './components/Form';
import {HoxRoot} from "hox";
import React from 'react'
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
        ...props
    }
) {
    const validator = "validator" in props ? props.validator : defineValidator(getUiOptions("uiSchema" in props ? props.uiSchema : {}).language || ("language" in props ? props.language : 'en_US'))
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
            liveValidate={true}
            omitExtraData={true}
            editOnChange={null}
            preSubmit={null}
            postSubmit={null}
            showDebug={false}
            validator={validator}
            {...props}
        />
    </HoxRoot>
}

export {Form as default};

