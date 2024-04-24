import {createLayoutElement} from '../../../../core/fields/utils'
import {Modal, Tooltip} from "antd";
import {CloudOutlined} from "@ant-design/icons";
import './index.css'

const ArrayCloud = ({children, render, cloudUrl, ...props}) => {
        if (cloudUrl) {
            let instance, layout = {
                "path": ".",
                "uiSchema": {
                    "ui:onSelect": () => {
                        instance.destroy()
                    },
                    "ui:cloudUrl": "/item/data",
                    "ui:button": false,
                    "ui:field": "CloudDownloadField"
                }
            }

            if (typeof cloudUrl === 'string') {
                layout["uiSchema"]["ui:cloudUrl"] = cloudUrl
            } else {
                layout = {
                    ...layout, ...cloudUrl,
                    uiSchema: {...layout.uiSchema, ...cloudUrl.uiSchema}
                }
            }
            return <Tooltip key={'cloud'}>
                <CloudOutlined onClick={(event) => {
                    event.stopPropagation();
                    instance = Modal.confirm({
                        centered: true,
                        closable: true,
                        icon: null,
                        width: '90%',
                        wrapClassName: 'full-width-modal-confirm-content',
                        footer: null,
                        content: createLayoutElement({
                            key: 'cloud', layout, render, isArray: false
                        })
                    })
                }}{...props}/>
            </Tooltip>
        }
        return null
    }
;
export default ArrayCloud;