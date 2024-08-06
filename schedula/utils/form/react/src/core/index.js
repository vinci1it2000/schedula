import React from 'react';
import {
    BrowserRouter
} from 'react-router-dom';
import Form from './form'
import {
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains,
    createLayoutElement
} from "./fields/utils";
import ReactDOM from 'react-dom/client'
import getTheme from '../themes'
import { dereferenceSync } from 'dereference-json-schema';

async function renderForm(
    {
        element,
        schema,
        uiSchema,
        csrf_token,
        url = '/',
        name = "form",
        theme = 'antd',
        formContext = {},
        ...props
    }
) {
    return getTheme(theme).then(theme => {
        const root = ReactDOM.createRoot(element);
        root.render(<BrowserRouter>
            <Form
                csrf_token={csrf_token}
                schema={schema}
                uiSchema={dereferenceSync(uiSchema)}
                name={name}
                url={url}
                theme={theme}
                formContext={formContext}
                {...props}/>
        </BrowserRouter>);
    });
}

export {
    renderForm as default,
    Form,
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains,
    createLayoutElement
}