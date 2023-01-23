import {List, Alert} from 'antd';
import {useLocaleStore} from "../../models/locale";
import {useMemo} from "react";

const Errors = ({children, render, ...props}) => {
    const {form} = render.formContext
    const {errors} = form.state
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Errors')
    return useMemo(() => (errors && errors.length ? <Alert
        message={locale.title}
        description={<List
            size="small"
            dataSource={errors}
            renderItem={(item) => <List.Item>{item.stack}</List.Item>}
        />}
        style={{height: '100%', overflowY: 'auto'}}
        type="error"
        {...props}
    /> : null), [errors, locale, props])
}
export const domainErrors = ({children, render, ...props}) => {
    const {form} = render.formContext
    const {errors} = form.state
    return (errors && errors.length)
}
export default Errors;