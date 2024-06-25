import {Button, Flex, Form, Segmented, Space} from 'antd'
import {
    BulbOutlined,
    EditOutlined,
    ReloadOutlined,
    SaveOutlined
} from "@ant-design/icons";
import {useMemo, useState} from "react";
import {useLocaleStore} from "../../../models/locale";
import isEqual from "lodash/isEqual";


export default function SettingsForm(
    {
        key = 'SettingsForm',
        userInfo: {settings: initialSettings},
        urlSettings,
        formContext: {form, ...formContext},
        schema = {
            "properties": {}
        },
        uiSchema = {
            "ui:onlyChildren": true
        }
    }) {
    const {
        props: {
            widgets,
            fields,
            templates,
            components,
            notify
        }
    } = form
    const [edited, setEdited] = useState(initialSettings)
    const [_form] = Form.useForm();
    const [disabled, setDisabled] = useState(true);
    const SchedulaForm = components.Form
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Settings')
    const modified = useMemo(() => {
        return !isEqual(edited, initialSettings)
    }, [edited, initialSettings])
    return <Flex key={key} gap="middle" vertical>
        <div key={'control'}><Segmented
            options={[
                {value: true, icon: <BulbOutlined/>},
                {value: false, icon: <EditOutlined/>},
            ]}
            onChange={setDisabled}/></div>
        <SchedulaForm
            key='form'
            disabled={disabled}
            form={_form}
            precompiledValidator={false}
            formData={disabled ? initialSettings : edited}
            csrf_token={form.state.csrf_token}
            schema={schema}
            uiSchema={uiSchema}
            name={'user-settings'}
            preSubmit={({formData}) => (formData)}
            postSubmit={({data: {user}}) => (user)}
            onChange={({formData}) => {
                setEdited(formData)
            }}
            onSubmit={({formData}) => {
                form.setState((state) => ({
                    ...state,
                    userInfo: formData,
                    submitCount: state.submitCount + 1
                }))
                setDisabled(true)
            }}
            url={urlSettings}
            theme={{widgets, fields, templates, components, notify}}
            formContext={formContext}>
            {disabled ? null : (form) => (<Space>
                <Button type="primary"
                        disabled={!modified}
                        icon={<SaveOutlined/>}
                        onClick={(event) => {
                            form.onSubmit(null, {})
                        }}>
                    {locale.submitButton}
                </Button>
                <Button icon={<ReloadOutlined/>} onClick={() => {
                    form.setState((state) => ({
                        ...state,
                        formData: initialSettings
                    }))
                    setEdited(initialSettings)
                }} disabled={!modified}>
                    {locale.revertButton}
                </Button>
            </Space>)}
        </SchedulaForm>
    </Flex>
}