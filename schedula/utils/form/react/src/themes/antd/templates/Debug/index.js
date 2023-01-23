import React, {useState, useCallback} from 'react'
import {DraggableModal} from 'ant-design-draggable-modal'
import {FloatButton} from 'antd';
import {
    QuestionCircleOutlined, CloseCircleOutlined
} from '@ant-design/icons';
import {useLocaleStore} from '../../models/locale'

const Debug = ({src, name, ...props}) => {
    const [visible, setVisible] = useState(false)
    const onOk = useCallback(() => setVisible(true), [])
    const onCancel = useCallback(() => setVisible(false), [])
    const onToggle = useCallback(() => setVisible(v => !v), [])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('DebugTemplate')
    return (<>
            <FloatButton
                tooltip={locale.tooltipFloatButton}
                icon={visible ? <CloseCircleOutlined/> :
                    <QuestionCircleOutlined/>}
                type="error"
                style={{right: 24}}
                size="small"
                onClick={onToggle}/>
            <DraggableModal
                locale={getLocale('Modal')} open={visible}
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
            </DraggableModal>
        </>
    );
};
export default Debug;