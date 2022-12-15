import {Form as BaseForm} from "@rjsf/mui";
import ReactDOM from 'react-dom/client'
import {customizeValidator} from "@rjsf/validator-ajv6";
import React, {useState, useEffect} from 'react';
import {
    ArrayField,
    ObjectField,
    isEmpty
} from "./components/layout";
import ErrorList from "./components/error"
import {JSONUpload, JSONExport} from "./components/io";
import {
    Backdrop,
    CircularProgress,
    Alert,
    AlertTitle,
    Modal
} from '@mui/material';
import hash from 'object-hash'
import cloneDeep from 'lodash/cloneDeep'

const validator = customizeValidator({ajvOptionsOverrides: {$data: true}})

validator.ajv.addKeyword('date-greater', {
    $data: true,
    validate: function dateGreater(threshold, date, parentSchema) {
        threshold = new Date(threshold)
        threshold.setDate(threshold.getDate() + (parentSchema.days || 0))
        date = new Date(date)
        if (threshold < date) {
            return true
        } else {
            dateGreater.errors = [
                {
                    keyword: 'date-greater',
                    message: `'${date.toISOString()}' should be greater than ${threshold.toISOString()}.`,
                    params: {keyword: 'date-greater'}
                }
            ];
            return false
        }
    }
});
validator.ajv.addKeyword('date-lower', {
    $data: true,
    validate: function dateLower(threshold, date, parentSchema) {
        threshold = new Date(threshold)
        threshold.setDate(threshold.getDate() + (parentSchema.days || 0))
        date = new Date(date)
        if (threshold > date) {
            return true
        } else {
            dateLower.errors = [
                {
                    keyword: 'date-lower',
                    message: `'${date.toISOString()}' should be lower than ${threshold.toISOString()}.`,
                    params: {keyword: 'date-lower'}
                }
            ];
            return false
        }
    }
});
const templates = {ErrorListTemplate: ErrorList};
const fields = {
    ArrayField,
    ObjectField,
    upload: JSONUpload,
    export: JSONExport
};


async function postData(url = '', data = {}, csrf_token) {
    const response = await fetch(url, {
        method: 'POST',
        crossDomain: true,
        //mode: 'no-cors', // no-cors, *cors, same-origin
        cache: 'no-cache', // *default, no-cache, reload, force-cache, only-if-cached
        //credentials: 'same-origin', // include, *same-origin, omit
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf_token
            //'Access-Control-Allow-Origin': '*'
            // 'Content-Type': 'application/x-www-form-urlencoded',
        },
        redirect: 'follow', // manual, *follow, error
        referrerPolicy: 'unsafe-url', // no-referrer, *no-referrer-when-downgrade, origin, origin-when-cross-origin, same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
        body: JSON.stringify(data) // body data type must match "Content-Type" header
    }).then(response => {
        if (response.redirected) {
            window.location.href = response.url;
        }
        return response
    });
    return response.json(); // parses JSON response into native JavaScript objects
}


function Form(
    {
        schema,
        csrf_token,
        uiSchema = {},
        url = '/',
        name = "form",
        formContext = {},
        editOnChange = null,
        preSubmit = null,
        postSubmit = null,
        ...props
    }
) {
    const [spinner, setSpinner] = useState(true);
    const [formData, setFormData] = useState(props.formData || {});
    delete props.formData
    var form;
    const [errorMessage, setErrorMessage] = useState("");
    const formatData = (data) => {
        data = Object.assign({}, data);
        delete data.hash;
        data.hash = hash(data)
        return data
    }
    const onSubmit = ({formData}, e) => {
        e.preventDefault();
        setSpinner(true)
        let input = preSubmit ? preSubmit({
            input: formData.input,
            formData,
            formContext,
            schema,
            uiSchema,
            csrf_token,
            ...props
        }) : formData.input;
        postData(url, input, csrf_token).then((data) => (
            postSubmit ? postSubmit({
                data,
                input: formData.input,
                formData,
                formContext,
                schema,
                uiSchema,
                csrf_token,
                ...props
            }) : data
        )).then((data) => {
            setFormData(formatData(Object.assign({input: formData.input}, data)))
        }).catch(error => {
            setFormData(formatData(Object.assign({input: formData.input}, {error: error.message})))
        }).finally((data) => {
            setSpinner(false)
        });
    }
    const onChange = ({formData, errors}) => {
        if (editOnChange) {
            let oldHash = hash(formData),
                newFormData = editOnChange({
                    formData: cloneDeep(formData),
                    formContext,
                    schema,
                    uiSchema,
                    csrf_token,
                    ...props
                });
            if (oldHash !== hash(newFormData)) {
                formData = formatData(newFormData)
                if (form)
                    form.setState(Object.assign({}, form.state, {formData}))
            }
        }
        if (!formData.hash) {
            formData = formatData(formData)
        }
        if (formData.hasOwnProperty('return')) {
            let hasReturn = !isEmpty(formData.return);
            if (hasReturn && formData.hash !== formatData(formData).hash) {
                delete formData.return;
                delete formData.hash;
            }
        }

        if (formData.hasOwnProperty('error') && typeof (formData.error) === 'string') {
            let error = formData.error;
            delete formData.error;
            setErrorMessage(error)
        }
        setFormData(formData)
    }

    useEffect(() => {
        setTimeout(() => setSpinner(false), 1000)
    }, []);
    if (!formContext.hasOwnProperty('$id'))
        formContext.$id = name
    return (
        <div id={name}>
            <Backdrop
                sx={{
                    color: '#fff',
                    zIndex: (theme) => theme.zIndex.drawer + 1
                }}
                open={spinner}
            >
                <CircularProgress color="inherit"/>
            </Backdrop>
            <BaseForm
                key={name + '-Form'}
                id={name + '-Form'}
                schema={schema}
                uiSchema={uiSchema}
                formData={formData}
                fields={fields}
                ref={_form => {
                    form = _form;
                }}
                validator={validator}
                templates={templates}
                showErrorList={true}
                omitExtraData={true}
                liveValidate={true}
                onChange={onChange}
                onSubmit={onSubmit}
                formContext={formContext}
                {...props}
            />
            <Modal
                key={name + "-error-modal"}
                open={errorMessage !== ""}
                onClose={() => {
                    setErrorMessage("")
                }}
                aria-labelledby="error-modal-title"
                aria-describedby="error-modal-description"
            >
                <Alert variant="outlined" severity="error" sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    minWidth: 400,
                    p: 4, bgcolor: 'background.paper',
                }} onClose={() => {
                    setErrorMessage("")
                }}>
                    <AlertTitle>Error</AlertTitle>
                    {errorMessage}
                </Alert>
            </Modal>
        </div>
    );
}

async function renderForm(
    {
        element,
        schema,
        uiSchema,
        url = '/',
        name = "form", ...props
    }
) {
    const root = ReactDOM.createRoot(element);
    root.render(
        <React.StrictMode>
            <Form schema={schema} uiSchema={uiSchema}
                  name={name}
                  url={url} {...props}/>
        </React.StrictMode>
    );
}

export {renderForm, Form as default};

