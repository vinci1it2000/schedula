import {Button, Flex, Form, Segmented, Space} from 'antd'
import {
    BulbOutlined,
    EditOutlined,
    ReloadOutlined,
    SaveOutlined
} from "@ant-design/icons";
import {useCallback, useMemo, useState} from "react";
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
        theme,
        SchedulaForm,
        csrf_token
    } = useMemo(() => {
        const {
            props: {
                widgets,
                fields,
                templates,
                components,
                notify
            },
            state: {csrf_token}
        } = form
        const SchedulaForm = components.Form
        const theme = {widgets, fields, templates, components, notify}
        return {
            csrf_token,
            theme,
            SchedulaForm
        }
    }, [form])
    const [edited, setEdited] = useState(initialSettings)
    const [_form] = Form.useForm();
    const [disabled, setDisabled] = useState(true);
    const {getLocale} = useLocaleStore()
    const locale = getLocale('User.Settings')
    const modified = useMemo(() => {
        return !isEqual(edited, initialSettings)
    }, [edited, initialSettings])
    const formData = useMemo(() => {
        return disabled ? initialSettings : edited
    }, [disabled])
    const preSubmit = useCallback(({formData}) => (formData), [])
    const postSubmit = useCallback(({data: {user}}) => (user), [])
    const onChange = useCallback(({formData}) => {
        setEdited(formData)
    }, [])
    const onSubmit = useCallback(({formData}) => {
        form.setState((state) => ({
            ...state,
            userInfo: formData,
            submitCount: state.submitCount + 1
        }))
        setDisabled(true)
    }, [form])
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
            formData={formData}
            csrf_token={csrf_token}
            schema={schema}
            uiSchema={uiSchema}
            name={'user-settings'}
            preSubmit={preSubmit}
            postSubmit={postSubmit}
            onChange={onChange}
            onSubmit={onSubmit}
            url={urlSettings}
            theme={theme}
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