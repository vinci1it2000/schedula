import {Upload as AntUpload, Modal as AntModal} from "antd"
import {useCallback, useMemo, useRef, useState} from "react"
import {Cropper} from 'react-advanced-cropper';
import 'react-advanced-cropper/dist/style.css';

const ImgCrop = (props) => {
    const {
        quality = 0.4,

        modalClassName,
        modalTitle,
        modalWidth,
        modalOk,
        modalCancel,
        onModalOk,
        onModalCancel,
        modalProps,

        cropperProps: {stencilProps, ...cropperProps} = {},

        beforeCrop,
        children
    } = props
    const cropperRef = useRef(null);
    const cb = useRef({})
    cb.current.onModalOk = onModalOk
    cb.current.onModalCancel = onModalCancel
    cb.current.beforeCrop = beforeCrop

    /**
     * upload
     */
    const [modalImage, setModalImage] = useState("")
    const onCancel = useRef()
    const onOk = useRef()

    const runBeforeUpload = useCallback(
        async ({beforeUpload, file, resolve, reject}) => {
            const rawFile = file

            if (typeof beforeUpload !== "function") {
                resolve(rawFile)
                return
            }

            try {
                // https://ant.design/components/upload-cn#api
                // https://github.com/ant-design/ant-design/blob/master/components/upload/Upload.tsx#L152-L178
                const result = await beforeUpload(file, [file])

                if (result === false) {
                    resolve(false)
                } else {
                    resolve((result !== true && result) || rawFile)
                }
            } catch (err) {
                reject(err)
            }
        },
        []
    )

    const getNewBeforeUpload = useCallback(
        beforeUpload => {
            return (file, fileList) => {
                return new Promise(async (resolve, reject) => {
                    let processedFile = file

                    if (typeof cb.current.beforeCrop === "function") {
                        try {
                            const result = await cb.current.beforeCrop(file, fileList)
                            if (result === false) {
                                return runBeforeUpload({
                                    beforeUpload,
                                    file,
                                    resolve,
                                    reject
                                }) // not open modal
                            }
                            if (result !== true) {
                                processedFile = result || file // will open modal
                            }
                        } catch (err) {
                            return runBeforeUpload({
                                beforeUpload,
                                file,
                                resolve,
                                reject
                            }) // not open modal
                        }
                    }

                    // read file
                    const reader = new FileReader()
                    reader.addEventListener("load", () => {
                        if (typeof reader.result === "string") {
                            setModalImage(reader.result) // open modal
                        }
                    })
                    reader.readAsDataURL(processedFile)

                    // on modal cancel
                    onCancel.current = () => {
                        setModalImage("")

                        let hasResolveCalled = false

                        cb.current.onModalCancel?.(LIST_IGNORE => {
                            resolve(LIST_IGNORE)
                            hasResolveCalled = true
                        })

                        if (!hasResolveCalled) {
                            resolve(AntUpload.LIST_IGNORE)
                        }
                    }

                    // on modal confirm
                    onOk.current = async event => {
                        setModalImage("")
                        const canvas = cropperRef.current?.getCanvas()
                        const {type, name, uid} = processedFile
                        canvas.toBlob(
                            async blob => {
                                const newFile = new File([blob], name, {type})
                                Object.assign(newFile, {uid})

                                runBeforeUpload({
                                    beforeUpload,
                                    file: newFile,
                                    resolve: file => {
                                        resolve(file)
                                        cb.current.onModalOk?.(file)
                                    },
                                    reject: err => {
                                        reject(err)
                                        cb.current.onModalOk?.(err)
                                    }
                                })
                            },
                            type,
                            quality
                        )
                    }
                })
            }
        },
        [cropperRef, quality, runBeforeUpload]
    )

    const getNewUpload = useCallback(
        children => {
            const upload = Array.isArray(children) ? children[0] : children
            const {beforeUpload, accept, ...restUploadProps} = upload.props

            return {
                ...upload,
                props: {
                    ...restUploadProps,
                    accept: accept || "image/*",
                    beforeUpload: getNewBeforeUpload(beforeUpload)
                }
            }
        },
        [getNewBeforeUpload]
    )

    /**
     * modal
     */
    const modalBaseProps = useMemo(() => {
        const obj = {}
        if (modalWidth !== undefined) obj.width = modalWidth
        if (modalOk !== undefined) obj.okText = modalOk
        if (modalCancel !== undefined) obj.cancelText = modalCancel
        return obj
    }, [modalCancel, modalOk, modalWidth])


    const title = modalTitle || "Edit image"

const defaultSize = ({ imageSize, visibleArea }) => {
            return {
                width: (visibleArea || imageSize).width,
                height: (visibleArea || imageSize).height,
            };
    }
    return (
        <>
            {getNewUpload(children)}
            {modalImage && (
                <AntModal
                    {...modalProps}
                    {...modalBaseProps}
                    open
                    title={title}
                    onCancel={onCancel.current}
                    onOk={onOk.current}
                    wrapClassName={modalClassName}
                    maskClosable={false}
                    destroyOnClose
                >
                    <Cropper
                        className="cropper"
                        ref={cropperRef}
                        src={modalImage}
                        defaultSize={defaultSize}
                        stencilProps={{
                            grid: true,
                            ...stencilProps
                        }}
                        {...cropperProps}
                    />
                </AntModal>
            )}
        </>
    )
}


export default ImgCrop
