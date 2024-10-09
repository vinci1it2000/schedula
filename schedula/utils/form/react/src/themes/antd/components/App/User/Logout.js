import {
    Button,
    Form
} from 'antd'
import {useLocaleStore} from "../../../models/locale";
import {useCallback} from "react";

export default function LogoutForm(
    {form, urlLogout, setOpen, setAuth, setSpinning}) {
    const onFinish = useCallback(() => {
        setSpinning(true)
        form.postData({
            url: urlLogout,
        }, () => {
            setSpinning(false)
            form.setState((state) => ({
                ...state, userInfo: {},
                submitCount: state.submitCount + 1
            }))
            setOpen(false)
            setAuth('login')
        }, () => {
            setSpinning(false)
        })
    }, [form, urlLogout, setOpen, setAuth, setSpinning])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Logout')
    return <Form
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        onFinish={onFinish}>
        <Form.Item>
            <Button type="primary" htmlType="submit" style={{width: '100%'}}>
                {locale.submitButton}
            </Button>
        </Form.Item>
    </Form>
}