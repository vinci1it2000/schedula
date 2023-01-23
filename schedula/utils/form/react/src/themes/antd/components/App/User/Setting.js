import {
    Button,
    Form,
    Input,
    Space
} from 'antd'
import {useState} from "react";
import {IdcardOutlined, SaveOutlined, ReloadOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../../models/locale";
import post from "../../../../../core/utils/fetch";
import isEqual from "lodash/isEqual";
import pick from "lodash/pick"

export default function SettingsForm(
    {form, userInfo, urlSettings, setOpen, setSpinning}) {
    const [field_errors, setFieldErrors] = useState({});
    const [_form] = Form.useForm();
    const onFinish = (data) => {
        setSpinning(true)
        post({
            url: urlSettings,
            data,
            form
        }).then(({data, messages}) => {
            setSpinning(false)
            if (messages)
                messages.forEach(([type, message]) => {
                    form.props.notify({type, message})
                })
            if (data.error) {
                form.props.notify({
                    message: locale.errorTitle,
                    description: (data.errors || [data.error]).join('\n'),
                })
                if (data.field_errors) {
                    setFieldErrors(data.field_errors || {})
                }
            } else {
                const {response = {}} = data
                const {user = {}} = response
                form.setState({
                    ...form.state,
                    userInfo: user,
                    submitCount: form.state.submitCount + 1
                })
                setOpen(false)
            }
        }).catch(error => {
            setSpinning(false)
            form.props.notify({
                message: locale.errorTitle,
                description: error.message,
            })
        })
    }
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Setting')
    const initialValues = pick(userInfo, ['firstname', 'lastname'])
    const [edited, setEdited] = useState(false)

    return <Form
        form={_form}
        style={{maxWidth: '300px', margin: 'auto', paddingBottom: '15px'}}
        initialValues={initialValues}
        onValuesChange={(_, allValues) => {
            setEdited(!isEqual(allValues, initialValues))
        }}
        onFinish={onFinish}>
        <Form.Item
            name="firstname"
            validateStatus={field_errors.firstname ? "error" : undefined}
            help={field_errors.firstname}
            rules={[{
                required: true,
                message: locale.firstnameRequired
            }]}>
            <Input
                prefix={<IdcardOutlined className="site-form-item-icon"/>}
                placeholder={locale.firstnamePlaceholder} onChange={() => {
                if (field_errors.firstname)
                    setFieldErrors({...field_errors, firstname: undefined})
            }}/>
        </Form.Item>
        <Form.Item
            name="lastname"
            validateStatus={field_errors.lastname ? "error" : undefined}
            help={field_errors.lastname}
            rules={[{
                required: true,
                message: locale.lastnameRequired
            }]}>
            <Input
                prefix={<IdcardOutlined className="site-form-item-icon"/>}
                placeholder={locale.lastnamePlaceholder} onChange={() => {
                if (field_errors.lastname)
                    setFieldErrors({...field_errors, lastname: undefined})
            }}/>
        </Form.Item>
        <Form.Item>
            <Space>
                <Button type="primary" htmlType="submit" disabled={!edited}
                        icon={<SaveOutlined/>}>
                    {locale.submitButton}
                </Button>
                <Button icon={<ReloadOutlined/>} onClick={() => {
                    _form.setFieldsValue(initialValues)
                    setEdited(false)
                }} disabled={!edited}>
                    {locale.revertButton}
                </Button>
            </Space>
        </Form.Item>
    </Form>
}