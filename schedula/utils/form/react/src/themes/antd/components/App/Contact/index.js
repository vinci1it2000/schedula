import React, {Suspense, useState} from 'react';

import {MessageOutlined} from "@ant-design/icons";
import {Drawer, Spin, Tooltip, Button} from "antd";
import {useLocaleStore} from "../../../models/locale";

const ContactForm = React.lazy(() => import( "./Contact"))
const ContactNav = ({key, form, formContext, urlContact, containerRef}) => {
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
            getContainer={containerRef.current}
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