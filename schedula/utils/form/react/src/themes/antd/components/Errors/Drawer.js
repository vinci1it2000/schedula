import {List, Drawer, theme} from 'antd';
import {useLocaleStore} from "../../models/locale";
import React, {useMemo} from "react";

const {useToken} = theme;

const Errors = ({children, render, ...props}) => {
    const {form} = render.formContext
    const {errors} = form.state
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Errors')
    const {token} = useToken();
    const drawerStyles = {
        body: {background: token.colorErrorBg},
        header: {background: token.colorErrorBg},
        footer: {background: token.colorErrorBg}
    };

    return useMemo(() => (errors && errors.length ? <Drawer
        title={locale.title}
        closable
        open={true}
        styles={drawerStyles}
        key={'error'} {...props}>
        <List
            size="small"
            style={{height: '100%', overflowY: 'auto'}}
            dataSource={errors}
            renderItem={(item) => <List.Item>{item.stack}</List.Item>}
        />
    </Drawer> : null), [errors, locale.title, drawerStyles, props])
}
export const domainErrors = ({children, render, ...props}) => {
    const {form} = render.formContext
    const {errors} = form.state
    return (errors && errors.length)
}
export default Errors;