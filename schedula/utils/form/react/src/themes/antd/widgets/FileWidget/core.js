import {UploadOutlined} from '@ant-design/icons';
import {Button, Tooltip, notification, Upload} from 'antd';
import update from 'immutability-helper';
import {useCallback, useRef, useState, useEffect} from 'react';
import {DndProvider, useDrag, useDrop} from 'react-dnd';
import {HTML5Backend} from 'react-dnd-html5-backend';
import './FileWidget.css'
import isEqual from "lodash/isEqual";
import format from 'python-format-js'
import {useLocaleStore} from '../../models/locale'

const type = 'DraggableUploadList';
const DraggableUploadListItem = (
    {originNode, moveRow, file, fileList, locale}) => {
    const ref = useRef(null);
    const index = fileList.indexOf(file);
    const [{isOver, dropClassName}, drop] = useDrop({
        accept: type,
        collect: (monitor) => {
            const {index: dragIndex} = monitor.getItem() || {};
            if (dragIndex === index) {
                return {};
            }
            return {
                isOver: monitor.isOver(),
                dropClassName: dragIndex < index ? ' drop-over-downward' : ' drop-over-upward',
            };
        },
        drop: (item) => {
            moveRow(item.index, index);
        },
    });
    const [, drag] = useDrag({
        type,
        item: {
            index,
        },
        collect: (monitor) => ({
            isDragging: monitor.isDragging(),
        }),
    });
    drop(drag(ref));
    const errorNode = <Tooltip title={locale.errorToolTip}>
        {originNode.props.children}
    </Tooltip>;
    return (
        <div
            ref={ref}
            className={`ant-upload-draggable-list-item ${isOver ? dropClassName : ''}`}
            style={{cursor: 'move'}}>
            {file.status === 'error' ? errorNode : originNode}
        </div>
    );
};

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
    const [fileList, setFileList] = useState((value ? (multiple ? value : [value]) : []).filter(
        v => !!v
    ).map(dataURLtoFile))

    let nFiles = fileList.length
    useEffect(() => {
        if (!fileList.some(file => file.status === 'uploading')) {
            let objFiles = fileList.filter(file => file.status === 'done').map(file => file.response),
                files = (value ? (multiple ? value : [value]) : []).filter(v => !!v);
            if (!isEqual(files, objFiles))
                onChange(multiple ? objFiles : objFiles[0])
        }
    }, [fileList, multiple, onChange, value])

    const moveRow = useCallback(
        (dragIndex, hoverIndex) => {
            const dragRow = fileList[dragIndex];
            setFileList(update(fileList, {
                $splice: [
                    [dragIndex, 1],
                    [hoverIndex, 0, dragRow],
                ],
            }));
        },
        [fileList, setFileList],
    );

    let props = {
        onRemove: (file) => {
            const index = fileList.indexOf(file);
            const newFileList = fileList.slice();
            newFileList.splice(index, 1);
            setFileList(newFileList)
        },
        beforeUpload: (file) => {
            let fn = file.name.split('.'),
                ext = fn[fn.length - 1].toLowerCase(),
                isAccepted = !(options.accept && options.accept.length) || options.accept.some(v => ext === v);
            if (!isAccepted) {
                const fileTypes = options.accept.map(
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
        onChange: (info) => {
            if (info.file.status === 'done') {
                setFileList((fileList) => {
                    const index = fileList.map(file => file.uid).indexOf(info.file.uid);
                    const newFileList = fileList.slice();
                    newFileList[index] = info.file
                    return newFileList
                })
            }
        },
        customRequest: async (
            {onProgress, onError, onSuccess, file}) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => {
                let url = reader.result.replace(
                    ";base64", `;name=${encodeURIComponent(file.name)};base64`
                )
                onSuccess(url)
            };
            reader.onerror = error => onError(error);
            reader.onprogress = function progress(e) {
                if (e.total > 0) {
                    e.percent = (e.loaded / e.total) * 100;
                }
                onProgress(e);
            };
            setFileList((fileList) => [...fileList, file])
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
        fileList
    }
    if (options.accept) {
        props.accept = `.${options.accept.join(',.')}`
    }
    if (multiple) {
        props.itemRender = (originNode, file, currFileList) => (
            <DraggableUploadListItem
                locale={locale}
                originNode={originNode}
                file={file}
                fileList={currFileList}
                moveRow={moveRow}
            />
        )
        if (schema.maxItems) {
            props.maxCount = schema.maxItems
        }
    } else {
        props.maxCount = 1
    }

    return (
        <DndProvider key={id + '-DndProvider'} backend={HTML5Backend}>
            <Upload key={id + '-Upload'} {...props}>
                {readonly || disabled ? null :
                    <Button
                        key={id + '-Button'}
                        icon={<UploadOutlined/>}
                        danger={!!rawErrors}>
                        {locale.dropMessage}
                    </Button>}
            </Upload>
        </DndProvider>
    );
};


export default FileWidget;