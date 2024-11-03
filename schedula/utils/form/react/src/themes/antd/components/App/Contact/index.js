import React, {Suspense, useState} from 'react';

import {MessageOutlined} from "@ant-design/icons";
import {Drawer, Spin, Tooltip, Button} from "antd";
import {useLocaleStore} from "../../../models/locale";

const getContainerElement = (refContainer) => {
    if (refContainer === null) {
        return null; // Return null if refContainer is null
    } else if (typeof refContainer === 'string') {
        return document.querySelector(refContainer); // Use the string selector
    } else if (refContainer && refContainer.current) {
        return refContainer.current; // Use the ref
    }
    return null; // Fallback if none of the conditions match
};
const ContactForm = React.lazy(() => import( "./Contact"))
const ContactNav = ({key, render: {formContext}, urlContact, containerRef}) => {
    const {form} = formContext
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Contact')
    const page = window.location.hash.slice(1)
    const [spinning, setSpinning] = useState(false);
    const [open, setOpen] = useState(page === 'contact');
    return <div key={key}>
        <Tooltip
            key={'btn'} title={locale.buttonTooltip} placement="bottomRight">
            <Button
                shape="circle" icon={<MessageOutlined/>}
                onClick={() => {
                    setOpen(true)
                }}
            />
        </Tooltip>
        <Drawer
            rootStyle={{position: "absolute"}}
            title={locale.title}
            closable={!spinning}
            onClose={() => {
                if (!spinning)
                    setOpen(false)
            }}
            getContainer={() => getContainerElement(containerRef)}
            open={open}>
            <Spin key={'page'} spinning={spinning}>
                <Suspense>
                    <ContactForm
                        key={'contact'}
                        form={form}
                        formContext={formContext}
                        urlContact={urlContact}
                        setSpinning={setSpinning}
                        setOpen={setOpen}/>
                </Suspense>
            </Spin>
        </Drawer>
    </div>
}
export default ContactNav;