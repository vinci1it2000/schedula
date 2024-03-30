import {notification, Upload, Modal} from 'antd';
import {useState, useEffect} from 'react';
import format from 'python-format-js'
import {useLocaleStore} from '../../models/locale'
import ImgCrop from 'antd-img-crop';


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
    file.url = dataurl
    file.preview = dataurl
    file.status = 'done'
    return file;
}


const ImageFileWidget = (
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
    const {accept, cropProps, ...opt} = options;
    const [previewOpen, setPreviewOpen] = useState(false);
    const [previewImage, setPreviewImage] = useState('');
    const [previewTitle, setPreviewTitle] = useState('');
    const [fileList, setFileList] = useState([])
    let nFiles = fileList.length
    const newValue = value ? (multiple ? value : [value]) : []
    useEffect(() => {
        setFileList((value ? (multiple ? value : [value]) : []).filter(
            v => !!v
        ).map(dataURLtoFile))
    }, [value, multiple])
    const handleCancelPreview = () => setPreviewOpen(false);

    const onRemove = (file) => {
        if (!multiple) {
            onChange(undefined)
        } else {
            const index = fileList.indexOf(file);
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
        onPreview: async (file) => {
            setPreviewImage(file.response);
            setPreviewOpen(true);
            setPreviewTitle(file.name);
        },
        showUploadList: {
            showDownloadIcon: true,
            showPreviewIcon: true,
            showRemoveIcon: !(readonly || disabled),
        },
        multiple: !!multiple,
        fileList,
        ...opt
    }
    if (accept) {
        props.accept = `.${accept.join(',.')}`
    }
    props.maxCount = multiple ? schema.maxItems : 1
    let _cropProps = {
        quality: 1,
        aspectSlider: true,
        rotationSlider: true,
        showReset: true,
        ...cropProps
    }
    return <>
        <ImgCrop key={id + '-ImgCrop'} {..._cropProps}>
            <Upload
                key={id + '-Upload'}
                listType="picture-card"
                danger={!!rawErrors}
                {...props}>
                {readonly || disabled || nFiles >= (props.maxCount || Infinity) ? null : locale.dropMessage}
            </Upload>
        </ImgCrop>
        <Modal
            key={id + '-Modal'} open={previewOpen} title={previewTitle}
            footer={null}
            onCancel={handleCancelPreview}>
            <img
                alt={previewTitle}
                style={{width: '100%'}}
                src={previewImage}
            />
        </Modal>
    </>;
};


export default ImageFileWidget;