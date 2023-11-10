import React, {Suspense} from 'react';
import Form from './form'
import {registerComponent, registerComponentDomain} from "./fields/utils";
import ReactDOM from 'react-dom/client'

async function renderForm(
    {
        element,
        schema,
        uiSchema,
        csrf_token,
        url = '/',
        name = "form",
        theme = null,
        formContext = {},
        ...props
    }
) {
    return new Promise((resolve, reject) => {
        if (theme) {
            resolve(theme)
        } else {
            import("../themes/antd").then(({generateTheme}) => {
                resolve(generateTheme(true))
            }).catch(err => {
                reject(err)
            });
        }
    }).then(theme => {
        const root = ReactDOM.createRoot(element);
        root.render(<Suspense>
            <Form
                csrf_token={csrf_token}
                schema={schema}
                uiSchema={uiSchema}
                name={name}
                url={url}
                theme={theme}
                formContext={formContext}
                {...props}/>
        </Suspense>);
    });
}

export {renderForm as default, registerComponent, registerComponentDomain}