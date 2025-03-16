import React, {useState, Suspense} from "react";
import {FloatButton, List, Badge, Modal} from 'antd';
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
            <Modal
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
            </Modal>
        </Suspense>
    );
};

export default ErrorList;