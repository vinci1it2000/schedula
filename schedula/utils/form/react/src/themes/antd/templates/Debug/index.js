import React, {useState, useCallback} from 'react'
import {FloatButton, Modal} from 'antd';
import {
    QuestionCircleOutlined, CloseCircleOutlined
} from '@ant-design/icons';
import {useLocaleStore} from '../../models/locale'

const Debug = ({src, name, ...props}) => {
    const [open, setOpen] = useState(false)
    const onOk = useCallback(() => setOpen(true), [])
    const onCancel = useCallback(() => setOpen(false), [])
    const onToggle = useCallback(() => setOpen(v => !v), [])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('DebugTemplate')
    return (<>
            <FloatButton
                tooltip={locale.tooltipFloatButton}
                icon={open ? <CloseCircleOutlined/> :
                    <QuestionCircleOutlined/>}
                type="error"
                style={{right: 24}}
                size="small"
                onClick={onToggle}/>
            <Modal
                locale={getLocale('Modal')} open={open}
                onOk={onOk} onCancel={onCancel}
                title={locale.titleModal}>
                <iframe
                    id={name + '-Form-debug'}
                    title={name + '-Form-debug'}
                    src={src}
                    allowFullScreen
                    style={{
                        height: '100%',
                        width: '100%',
                        border: "none"
                    }}>
                </iframe>
            </Modal>
        </>
    );
};
export default Debug;