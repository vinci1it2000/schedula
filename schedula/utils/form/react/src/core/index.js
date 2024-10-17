import React, {Suspense} from 'react';
import {
    registerComponent,
    registerComponentDomain,
    getComponents,
    getComponentDomains,
    createLayoutElement
} from "./fields/utils";
import ReactDOM from 'react-dom/client'
import getTheme from '../themes'
import {dereferenceSync} from 'dereference-json-schema';

const Form = React.lazy(() => import('./form'));

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
        root.render(<Suspense><Form
            csrf_token={csrf_token}
            schema={schema}
            uiSchema={dereferenceSync(uiSchema)}
            name={name}
            url={url}
            theme={theme}
            formContext={formContext}
            {...props}/></Suspense>);
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