import {
    Button,
    Form
} from 'antd'
import {useLocaleStore} from "../../../models/locale";

export default function LogoutForm(
    {form, urlLogout, setOpen, setAuth, setSpinning}) {
    const onFinish = () => {
        setSpinning(true)
        form.postData({
            url: urlLogout,
            data: {},
        }).then(({data: {error, errors}}) => {
            setSpinning(false)
            if (error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (errors || [error]).join('\n'),
                })
            } else {
                form.setState((state) => ({
                    ...state, userInfo: {},
                    submitCount: state.submitCount + 1
                }))
                setOpen(false)
                setAuth('login')
            }
        }).catch(({message}) => {
            setSpinning(false)
            form.props.notify({
                message: locale.errorTitle,
                description: message,
            })
        })
    }
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