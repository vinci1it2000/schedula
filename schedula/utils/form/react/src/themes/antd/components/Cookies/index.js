import React, {useState, useEffect, useMemo, useCallback} from 'react';
import {
    Modal,
    Button,
    Switch,
    Divider,
    Typography,
    FloatButton,
    Collapse,
    Flex,
    Space,
    Checkbox
} from 'antd';
import Markdown from '../Markdown'
import isEqual from 'lodash/isEqual';
import {SafetyOutlined} from '@ant-design/icons';
import {useLocaleStore} from "../../models/locale";

const {Title} = Typography

const Consent = (
    {
        id,
        value,
        description,
        title,
        setConsents,
        disabled,
        formData
    }
) => (
    <Space key={id} direction="vertical" gutter={[16]} style={{width: '100%'}}>
        <Title key={"title"} level={5} strong>{title}</Title>
        <Flex key={"content"} direction="row"
              justify="space-between" style={{width: '100%'}}>
            <Markdown render={{formData}} key="text">
                {description}
            </Markdown>
            <Switch
                key="control" value={value} disabled={disabled}
                onChange={(value) => {
                    setConsents((consents) => ({
                        ...consents, [id]: value
                    }))
                }}/>
        </Flex>
    </Space>)

const CookiesModal = (
    {
        children,
        render: {formContext: {form}, formData: {_formData}},
        urlConsent = '/gdpr/consent',
        consentItems: _consentItems,
        ...props
    }
) => {
    const formData = useMemo(() => {
        return {..._formData, urlConsent}
    }, [_formData, urlConsent])
    const {getLocale} = useLocaleStore()
    const locale = getLocale('Cookies')
    const [visible, setVisible] = useState(!localStorage.getItem('privacyConsentId'));
    const [loading, setLoading] = useState(true);
    const [consents, setConsents] = useState(null);
    const [newConsents, setNewConsents] = useState({});
    const updateConsents = useCallback(({id, consents}) => {
        consentItems.forEach(({key, default: default_value}) => {
            if (!(key in consents)) {
                consents[key] = default_value;
            }
        })
        localStorage.setItem('privacyConsentId', id || '');
        setConsents(consents)
        setNewConsents(consents)
    }, [])
    const postConsents = useCallback(() => {
        const consentId = localStorage.getItem('privacyConsentId');
        form.postData({
            url: urlConsent, data: {id: consentId, consents: newConsents},
        }, ({data}) => {
            updateConsents(data)
        })
    }, [newConsents, urlConsent, form, updateConsents, locale])
    const consentItems = useMemo(() => {
        return _consentItems || [{
            "key": "mandatory",
            "title": locale.titleMandatory,
            "description": locale.descriptionMandatory,
            "default": true,
            "disabled": true
        }, {
            "key": "functional",
            "title": locale.titleFunctional,
            "description": locale.descriptionFunctional,
            "default": true,
            "disabled": false
        }, {
            "key": "experience",
            "title": locale.titleExperience,
            "description": locale.descriptionExperience,
            "default": true,
            "disabled": false
        }, {
            "key": "measuring",
            "title": locale.titleMeasuring,
            "description": locale.descriptionMeasuring,
            "default": true,
            "disabled": false
        }, {
            "key": "marketing",
            "title": locale.titleMarketing,
            "description": locale.descriptionMarketing,
            "default": true,
            "disabled": false
        }]
    }, [locale])

    useEffect(() => {
        if (visible) {
            const consentId = localStorage.getItem('privacyConsentId');
            if (consentId) {
                setLoading(true);
                form.postData({
                    url: `${urlConsent}/${consentId}`, method: 'GET'
                }, ({data}) => {
                    updateConsents(data)
                    setLoading(false);
                }, () => {
                    setLoading(false);
                })
            } else {
                setNewConsents(consentItems.reduce((acc, {
                    key, default: default_value
                }) => {
                    acc[key] = default_value;
                    return acc;
                }, {}))
                setLoading(false);
            }
        }
    }, [visible, consentItems, form, urlConsent, updateConsents])
    const edited = useMemo(() => (consents !== null && !isEqual(newConsents, consents)), [newConsents, consents]);

    const allDisabled = consentItems.reduce((acc, {key, disabled}) => {
        return acc && (disabled || !newConsents[key])
    }, true)
    const allEnabled = consentItems.reduce((acc, {key, disabled}) => {
        return acc && (disabled || newConsents[key])
    }, true)
    return <>
        <Modal
            style={{
                bottom: 20, top: 'unset', left: 20, position: 'absolute',
                maxHeight: "calc(100vh - 40px)", overflowY: 'auto'
            }}
            title={locale.modalTitle}
            closable={consents !== null}
            onCancel={() => {
                if (consents !== null)
                    setVisible(false)
            }}
            loading={loading}
            open={visible}
            footer={[(consents === null || !edited ? <Button onClick={() => {
                if (consents === null) postConsents()
                setVisible(false)
            }}>
                {consents !== null ? locale.cancelButton : locale.rejectButton}
            </Button> : null), (consents === null || edited ?
                <Button type={"primary"} onClick={() => {
                    postConsents()
                    setVisible(false)
                }}>{edited ? locale.saveButton : locale.acceptButton} </Button> : null)]}
            width={"calc(100% - 40px)"}
            key="Modal">
            <Space direction="vertical" size="middle" style={{
                width: '100%'
            }}>
                <Markdown render={{formData}} key='intro'>
                    {locale.introText}
                </Markdown>
                <Divider key="divider"/>
                <Collapse
                    key={"options"}
                    items={[{
                        styles: {header: {alignItems: "center"}},
                        key: '1', label: locale.settingsText,
                        extra: <div onClick={(e) => {
                            e.stopPropagation()
                            setNewConsents(consents => consentItems.reduce((acc, {
                                key, disabled
                            }) => {
                                if (!disabled) acc[key] = !allEnabled
                                return acc
                            }, {...consents}))
                        }}>
                            <Checkbox
                                indeterminate={!(allEnabled || allDisabled)}
                                checked={!allDisabled}>
                                {locale.acceptAllButton}
                            </Checkbox>
                        </div>,
                        children: <Space
                            style={{
                                maxHeight: 200, overflowY: 'auto', width: '100%'
                            }}
                            direction="vertical" size="middle">
                            <Title key={'title'} level={5}>
                                {locale.settingsTitle}
                            </Title>
                            <Markdown render={{formData}} key={'intro'}>
                                {locale.settingsIntro}
                            </Markdown>

                            <Divider key="divider"/>
                            {consentItems.map(({key, ...item}) => <Consent
                                {...item}
                                formData={formData}
                                key={key}
                                id={key}
                                value={newConsents[key]}
                                setConsents={setNewConsents}/>)}
                        </Space>
                    }]}/>
            </Space>
        </Modal>
        {!visible ? <FloatButton
            key="settings"
            icon={<SafetyOutlined/>}
            onClick={() => {
                setVisible(true)
            }}
            style={{bottom: '16px', left: '16px'}}
            {...props}
        /> : null}
    </>
};

export default CookiesModal;