import React, {useState, Suspense} from "react";
import {FloatButton, List, Badge} from 'antd';
import {
    DraggableModal
} from 'ant-design-draggable-modal/packages/ant-design-draggable-modal'
import './index.css'
import {useLocaleStore} from "../../models/locale";

const ErrorList = ({errors}) => {
    const [open, setOpen] = useState(false);
    const showModal = () => {
        setOpen(!open);
    };
    const closeModal = (e) => {
        setOpen(false);
    };
    const {getLocale} = useLocaleStore()
    const locale = getLocale('ErrorListTemplate')
    return (
        <Suspense>
            <FloatButton
                tooltip={<div>{locale.tooltipFloatButton}</div>}
                description={locale.descriptionFloatButton}
                shape="square"
                onClick={showModal}
                icon={<Badge count={errors.length} overflowCount={999}/>}
                type="error"
                style={{right: 0, top: 88, height: 40}}
            />
            <DraggableModal
                locale={getLocale('Modal')}
                title={locale.titleModal}
                open={open}
                onOk={closeModal}
                onCancel={closeModal}
                initialHeight={400}
                footer={null}>
                <List
                    size="small"
                    dataSource={errors}
                    renderItem={(item) => <List.Item>{item.stack}</List.Item>}
                />
            </DraggableModal>
        </Suspense>
    );
};

export default ErrorList;