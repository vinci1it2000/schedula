import {UploadOutlined} from '@ant-design/icons';
import {Button, notification, Upload} from 'antd';
import {useState, useEffect} from 'react';
import './FileWidget.css'
import format from 'python-format-js'
import {useLocaleStore} from '../../models/locale'


function dataURLtoFile(dataurl) {
    let arr = dataurl.split(','),
        mime = arr[0].match(/:(.*?);/)[1],
        filename = decodeURIComponent(arr[0].match(/;?name=(.*?);/)[1]),
        bstr = atob(arr[1]),
        n = bstr.length,
        u8arr = new Uint8Array(n);

    while (n--) {
        u8arr[n] = bstr.charCodeAt(n);
    }
    let file = new File([u8arr], filename, {type: mime})
    file.response = dataurl
    file.status = 'done'
    return file;
}


const FileWidget = (
    {
        multiple,
        id,
        readonly,
        disabled,
        onChange,
        value,
        schema,
        options,
        rawErrors
    }) => {
    const {getLocale} = useLocaleStore()
    const locale = getLocale('FileWidget')
    const [fileList, setFileList] = useState([])
    const newValue = value ? (multiple ? value : [value]) : []
    let nFiles = fileList.length
    useEffect(() => {
        setFileList((value ? (multiple ? value : [value]) : []).filter(
            v => !!v
        ).map(dataURLtoFile))
    }, [value, multiple])
    const {accept, ...opt} = options;
    const onRemove = (file) => {
        if (!multiple) {
            onChange(undefined)
        } else {
            const index = fileList.indexOf(file);
            const newValue = value.slice();
            newValue.splice(index, 1);
            onChange(newValue)
        }
    }
    let props = {
        onRemove,
        beforeUpload: (file) => {
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
        },
        onDownload: (file) => {
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
        },
        onChange: ({file, fileList: newFileList}) => {
            if (file.status === 'done') {
                if (multiple) {
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
        },
        customRequest: async ({onProgress, onError, onSuccess, file}) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => {
                let url = reader.result.replace(
                    ";base64", `;name=${encodeURIComponent(file.name)};base64`
                )
                if (fileList.some(v => v.response === url)) {
                    notification.error({
                        message: locale.errorNotUploaded,
                        description: format(locale.errorSameFile, {filename: file.name}),
                        placement: 'top'
                    });
                    onError(url)
                } else {
                    onSuccess(url)
                }
            };
            reader.onerror = error => onError(error);
            reader.onprogress = function progress(e) {
                if (e.total > 0) {
                    e.percent = (e.loaded / e.total) * 100;
                }
                onProgress(e);
            };
            return {
                abort() {
                    reader.abort()
                }
            };
        },
        showUploadList: {
            showDownloadIcon: true,
            showRemoveIcon: !(readonly || disabled),
        },
        multiple: !!multiple,
        fileList,
        ...opt
    }
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

    return <Upload key={id + '-Upload'} {...props}>
        {readonly || disabled ? null :
            <Button
                key={id + '-Button'}
                icon={<UploadOutlined/>}
                danger={!!rawErrors}>
                {locale.dropMessage}
            </Button>}
    </Upload>

};


export default FileWidget;