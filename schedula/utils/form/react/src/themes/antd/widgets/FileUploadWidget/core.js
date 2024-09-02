import {UploadOutlined} from '@ant-design/icons';
import {Button, notification, Upload} from 'antd';
import {useState, useEffect, useMemo, useCallback} from 'react';
import './FileWidget.css'
import format from 'python-format-js'
import {useLocaleStore} from '../../models/locale'
import {sha512} from 'js-sha512';


function dataURLtoFile(dataurl) {
    const searchParams = new URLSearchParams(dataurl)
    return {
        status: 'done',
        response: dataurl,
        name: searchParams.get('name')
    };
}

const onDownload = (file) => {
    const a = document.createElement('a')
    a.download = file.name
    a.href = file.response
    const clickEvt = new MouseEvent('click', {
        view: window,
        bubbles: true,
        cancelable: true,
    })
    a.dispatchEvent(clickEvt)
    a.remove()
}
const FileUploadWidget = (
    {
        multiple,
        id,
        readonly,
        disabled,
        onChange,
        value,
        schema,
        options,
        rawErrors,
        formContext: {form}
    }) => {
    const {getLocale} = useLocaleStore()
    const locale = getLocale('FileWidget')
    const [fileList, setFileList] = useState([])

    let nFiles = fileList.length
    useEffect(() => {
        setFileList((value ? (multiple ? value : [value]) : []).filter(
            v => !!v
        ).map(dataURLtoFile))
    }, [value, multiple])
    const {accept, action, ...opt} = options;
    const onRemove = useCallback((file) => {
        if (!multiple) {
            onChange(undefined)
        } else {
            const index = fileList.map(({uid}) => uid).indexOf(file.uid);
            const newValue = value.slice();
            newValue.splice(index, 1);
            setFileList((value ? (multiple ? value : [value]) : []).filter(
                v => !!v
            ).map(dataURLtoFile))
            onChange(newValue)
        }
    }, [value, multiple, onChange, fileList])
    const beforeUpload = useCallback((file) => {
        let fn = file.name.split('.'),
            ext = fn[fn.length - 1].toLowerCase(),
            isAccepted = !(accept && accept.length) || accept.some(v => ext === v);
        if (!isAccepted) {
            const fileTypes = accept.map(
                v => v.toUpperCase()
            ).join('/')
            notification.error({
                message: locale.errorNotUploaded,
                description: format(locale.errorFileType, {fileTypes}),
                placement: 'top'
            })
        } else if (schema.maxItems && nFiles >= schema.maxItems) {
            isAccepted = false
            if (nFiles === schema.maxItems) {
                const maxItems = schema.maxItems
                notification.error({
                    message: locale.errorNotUploaded,
                    description: schema.maxItems > 1 ? format(locale.errorMaxItems, {maxItems}) : locale.errorOnlyOneItem,
                    placement: 'top'
                })
                nFiles++;
            }
        } else if (fileList.some(v => v.name === file.name)) {
            notification.error({
                message: locale.errorNotUploaded,
                description: format(locale.errorSameFile, {filename: file.name}),
                placement: 'top'
            });
            isAccepted = false
        }
        if (isAccepted) nFiles++;
        return isAccepted || Upload.LIST_IGNORE;
    }, [accept, fileList, locale, nFiles, schema.maxItems]);
    const onChange_ = useCallback(({file, fileList: newFileList}) => {
        if (file.status === 'done') {
            if (multiple) {
                const newValue = value ? (multiple ? value : [value]) : []
                newValue.push(file.response)
                onChange(newValue)
            } else {
                onChange(file.response)
            }
            setFileList(newFileList)
        } else if (file.status === 'error') {
            onRemove(file)
        } else if (file.status === 'uploading') {
            setFileList(newFileList)
        }
    }, [multiple, value, onChange, onRemove])
    const customRequest = useCallback(async (
        {onProgress, onError, onSuccess, file}
    ) => {
        const reader = new FileReader();
        reader.onload = () => {
            let filename = file.name,
                base64file = reader.result
            let onErrorPost = ({message}) => {
                onError(message)
            }
            form.postData({
                url: action,
                data: {
                    hash: sha512(base64file),
                    filename,
                }
            }, ({data: {sendfile = false, url}}) => {
                if (sendfile) {
                    form.postData({
                        url: action,
                        data: {
                            filename,
                            file: base64file
                        }
                    }, ({data: {url}}) => {
                        onSuccess(url)
                    }, onErrorPost)
                } else {
                    onSuccess(url)
                }
            }, onErrorPost)
        };
        reader.onerror = error => onError(error);
        reader.readAsDataURL(file);
        return {
            abort() {
                reader.abort()
            }
        };
    }, [form, action])
    const props = useMemo(() => {
        let props = {}
        if (accept) {
            props.accept = `.${accept.join(',.')}`
        }
        if (multiple) {
            if (schema.maxItems) {
                props.maxCount = schema.maxItems
            }
        } else {
            props.maxCount = 1
        }
        return props;
    }, [multiple, accept, schema.maxItems])

    return <Upload
        key={id + '-Upload'}
        onRemove={onRemove}
        beforeUpload={beforeUpload}
        onDownload={onDownload}
        onChange={onChange_}
        customRequest={customRequest}
        showUploadList={{
            showDownloadIcon: true,
            showRemoveIcon: !(readonly || disabled),
        }}
        multiple={!!multiple}
        fileList={fileList}
        {...props}
        {...opt}>
        {readonly || disabled ? null :
            <Button
                key={id + '-Button'}
                icon={<UploadOutlined/>}
                danger={!!rawErrors}>
                {locale.dropMessage}
            </Button>}
    </Upload>
};


export default FileUploadWidget;