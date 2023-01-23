import {withTheme} from './components/Form';
import {HoxRoot} from "hox";
import React from 'react'

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
            {...props}
        />
    </HoxRoot>
}

export {Form as default};

