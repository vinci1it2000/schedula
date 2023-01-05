import React, {useState, useEffect, Suspense} from 'react';
import ReactDOM from 'react-dom/client'
import {customizeValidator} from "@rjsf/validator-ajv8";
import jref from 'json-ref-lite';
import {
    ArrayField,
    ObjectField,
    isEmpty
} from "./components/layout";
import ErrorList from "./components/error"
import {JSONUpload, JSONExport} from "./components/io";
import hash from 'object-hash'
import FileWidget from "./widgets/files";
import {gzip} from 'pako';
import debounce from 'lodash/debounce'

const CloseIcon = React.lazy(() => import("@mui/icons-material/Close"));
const SchemaIcon = React.lazy(() => import('@mui/icons-material/Schema'));
const BaseForm = React.lazy(() => import("@rjsf/mui"));
const Backdrop = React.lazy(() => import('@mui/material/Backdrop'));
const CircularProgress = React.lazy(() => import('@mui/material/CircularProgress'));
const Alert = React.lazy(() => import('@mui/material/Alert'));
const AlertTitle = React.lazy(() => import('@mui/material/AlertTitle'));
const Modal = React.lazy(() => import('@mui/material/Modal'));
const Card = React.lazy(() => import('@mui/material/Card'));
const CardHeader = React.lazy(() => import('@mui/material/CardHeader'));
const CardContent = React.lazy(() => import('@mui/material/CardContent'));
const IconButton = React.lazy(() => import('@mui/material/IconButton'));
const Fab = React.lazy(() => import('@mui/material/Fab'));
const ReactModal = React.lazy(() => import('./components/modal'));
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
const widgets = {FileWidget};


async function postData(url = '', data = {}, csrf_token, method = 'POST', headers = {}) {
    return fetch(url, {
        method: method,
        crossDomain: true,
        //mode: 'no-cors', // no-cors, *cors, same-origin
        cache: 'no-cache', // *default, no-cache, reload, force-cache, only-if-cached
        //credentials: 'same-origin', // include, *same-origin, omit
        headers: Object.assign({
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf_token,
            'Content-Encoding': 'gzip',
            'Accept-Encoding': 'gzip'
            //'Access-Control-Allow-Origin': '*'
            // 'Content-Type': 'application/x-www-form-urlencoded',
        }, headers),
        redirect: 'follow', // manual, *follow, error
        referrerPolicy: 'unsafe-url', // no-referrer, *no-referrer-when-downgrade, origin, origin-when-cross-origin, same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
        body: gzip(JSON.stringify(data)) // body data type must match "Content-Type" header
    }).then(async (response) => {
        let debugUrl;
        if (response.headers.has('Debug-Location')) {
            debugUrl = response.headers.get('Debug-Location')
        }
        if (response.redirected) {
            window.location.href = response.url;
        }
        return {data: await response.json(), debugUrl}
    });
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
        formData = {},
        liveValidate = true,
        removeReturnOnChange = true,
        ...props
    }
) {
    let currentForm;
    const [dataState, setDataState] = useState({
        formData,
        hash: hash(formData)
    });

    const [errorState, setErrorState] = useState({
        errorMessage: "",
        openError: false
    });

    const [debugState, setDebugState] = useState({
        debugUrl: "",
        openDebug: false
    });

    const [spinner, setSpinner] = useState(true);
    const validateForm = debounce(() => {
        if (currentForm)
            currentForm.validateForm()
    }, 500)


    const onSubmit = ({formData}, e) => {
        e.preventDefault();
        let method = e.nativeEvent.submitter.getAttribute('formmethod') || 'POST',
            headers = JSON.parse(
                e.nativeEvent.submitter.getAttribute('headers') || '{}'
            );
        setDataState({formData, hash: hash(formData)})
        setDebugState({debugUrl: "", openDebug: false})
        setErrorState({openError: false, errorMessage: ""})
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
        postData(url, input, csrf_token, method, headers).then(
            ({data, debugUrl}) => {
                return {
                    debugUrl,
                    data: postSubmit ? postSubmit({
                        data,
                        input: formData.input,
                        formData,
                        formContext,
                        schema,
                        uiSchema,
                        csrf_token,
                        ...props
                    }) : data
                }
            }).then(({data, debugUrl}) => {
            if (debugUrl) {
                setDebugState({
                    debugUrl: debugUrl,
                    openDebug: true
                })
            }
            if (data.hasOwnProperty('error')) {
                setErrorState({
                    openError: true,
                    errorMessage: data.error
                })
            } else {
                formData = Object.assign({input: formData.input}, data)
                setDataState({formData, hash: hash(formData)})
            }
            validateForm()
            setSpinner(false)
        }).catch(error => {
            setErrorState({openError: true, errorMessage: error.message})
            setSpinner(false)
        });
    }
    const onChange = ({formData, errors}) => {
        if (currentForm) {
            let prevHash = hash(formData), forceUpdate = false,
                noReturn = isEmpty(formData.return || {});
            if (removeReturnOnChange && !noReturn && prevHash !== dataState.hash) {
                delete formData.return;
                noReturn = true
            }

            if (debugState.debugUrl && noReturn) {
                setDebugState({debugUrl: "", openDebug: false})
                forceUpdate = true
            }
            if (editOnChange) {
                formData = editOnChange({
                    formData,
                    formContext,
                    schema,
                    uiSchema,
                    csrf_token,
                    ...props
                });
            }

            let currentHash = hash(formData)
            if (forceUpdate || prevHash !== currentHash) {
                setDataState({formData, hash: currentHash})
            }
            if (liveValidate) {
                validateForm()
            }
        }
    }

    if (!formContext.hasOwnProperty('$id'))
        formContext.$id = name
    useEffect(() => {
        setTimeout(() => setSpinner(false), 300)
    });
    return (<Suspense>
        <div id={name}>
            {spinner ?
                <Backdrop
                    sx={{
                        color: '#fff',
                        zIndex: (theme) => theme.zIndex.drawer * 100
                    }}
                    open={spinner}
                >
                    <CircularProgress color="inherit"/>
                </Backdrop> : null}
            <BaseForm
                key={name + '-Form'}
                id={name + '-Form'}
                schema={schema}
                uiSchema={uiSchema}
                formData={dataState.formData}
                fields={fields}
                widgets={widgets}
                ref={(form) => {
                    if (form) {
                        currentForm = form;
                        let currentHash = hash(form.state.formData)
                        if (dataState.hash !== currentHash) {
                            setDataState({
                                formData: form.state.formData,
                                hash: currentHash
                            })
                            validateForm()
                        }
                    }
                }}
                validator={validator}
                templates={templates}
                showErrorList={'top'}
                omitExtraData={true}
                liveValidate={false}
                onChange={onChange}
                onSubmit={onSubmit}
                formContext={formContext}
                {...props}
            />
            <Modal
                key={name + "-error-modal"}
                open={errorState.openError}
                onClose={() => {
                    setErrorState(Object.assign({}, errorState, {openError: false}))
                }}
            >
                <Alert variant="outlined" severity="error" sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    minWidth: 400,
                    p: 4, bgcolor: 'background.paper',
                }} onClose={() => {
                    setErrorState(Object.assign({}, errorState, {openError: false}))
                }}>
                    <AlertTitle>Error</AlertTitle>
                    {errorState.errorMessage}
                </Alert>
            </Modal>
            {!debugState.debugUrl || debugState.openDebug ? null :
                <Fab
                    sx={{
                        position: 'fixed',
                        top: 135,
                        right: 16,
                        "z-index": 10000000000
                    }}
                    size="small" onClick={() => {
                    setDebugState(Object.assign({}, debugState, {openDebug: true}))
                }}>
                    <SchemaIcon/>
                </Fab>}
            <ReactModal
                disableKeystroke={true}
                onRequestClose={() => {
                    setDebugState(Object.assign({}, debugState, {openDebug: false}))
                }}
                isOpen={debugState.debugUrl && debugState.openDebug}>
                <Card sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                }}>
                    <CardHeader
                        sx={{"backgroundColor": "lightgray"}}
                        action={
                            <IconButton onClick={() => {
                                setDebugState(Object.assign({}, debugState, {openDebug: false}))
                            }}>
                                <CloseIcon/>
                            </IconButton>
                        } title={'Debug mode'}>
                    </CardHeader>
                    <CardContent sx={{flexGrow: 1}}>
                        {debugState.debugUrl ? <iframe
                            id={name + '-Form-debug'}
                            title={name + '-Form-debug'}
                            src={debugState.debugUrl}
                            allowFullScreen
                            style={{
                                height: '100%',
                                width: '100%',
                                border: "none"
                            }}>
                        </iframe> : null}
                    </CardContent>
                </Card>
            </ReactModal>
        </div>
    </Suspense>);
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
        <Suspense>
            <Form
                schema={jref.resolve(schema)}
                uiSchema={uiSchema}
                name={name}
                url={url} {...props}/>
        </Suspense>
    );
}

export {renderForm, Form as default};

