import {notification, Upload, theme, ConfigProvider} from 'antd';
import {useState, useEffect, useMemo, useCallback} from 'react';
import {InboxOutlined} from '@ant-design/icons';
import format from 'python-format-js'
import './DraggerFileWidget.css'
import {useLocaleStore} from '../../models/locale'


const {useToken} = theme;

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

const DraggerFileWidget = (
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
    const {token} = useToken();

    let nFiles = fileList.length
    useEffect(() => {
        setFileList((value ? (multiple ? value : [value]) : []).filter(
            v => !!v
        ).map(dataURLtoFile))
    }, [value, multiple])
    const {accept, ...opt} = options;
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
            let url = reader.result.replace(
                ";base64", `;name=${encodeURIComponent(file.name)};base64`
            )
            if (fileList.some(v => v.response === url)) {
                let description = format(locale.errorSameFile, {filename: file.name})
                notification.error({
                    message: locale.errorNotUploaded,
                    description,
                    placement: 'top'
                });
                onError(description)
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
        reader.readAsDataURL(file);
        return {
            abort() {
                reader.abort()
            }
        };
    }, [locale, fileList])
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
    const {Dragger} = Upload;
    const theme = useMemo(() => {
        let theme = {}
        if (!!rawErrors) {
            theme = {
                components: {
                    "Upload": {
                        "colorBorder": token.colorError,
                        "colorText": token.colorError,
                        "colorPrimary": token.colorError,
                        "colorPrimaryBorder": token.colorError,
                        "colorPrimaryHover": token.colorError,
                        "colorTextDescription": token.colorError,
                        "colorTextHeading": token.colorError
                    }
                }
            }
        }
        return theme
    }, [rawErrors, token])
    return <ConfigProvider theme={theme}>
        <Dragger
            key={id}
            disabled={readonly || disabled}
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
            <p className="ant-upload-drag-icon"><InboxOutlined/></p>
            <p className="ant-upload-text">{locale.dropMessage}</p>
        </Dragger>
    </ConfigProvider>

};

export default DraggerFileWidget;