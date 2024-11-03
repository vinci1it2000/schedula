import React, {useEffect, useState} from 'react';
import {Button, Dropdown} from 'antd';
import './Language.css'

const LanguageNav = ({render: {formContext: {form}}, languages}) => {
    const [languageOptions, setLanguageOptions] = useState(languages !== true ? languages : null);
    useEffect(() => {
        if (languages === true)
            form.postData({
                url: '/locales/languages.json',
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Encoding': 'gzip',
                    'Accept-Encoding': 'gzip'
                }
            }, ({data}) => {
                if (typeof data === 'object') {
                    setLanguageOptions(data)
                }
            }, () => {
                setLanguageOptions(null)
            })
    }, [languages, form]);
    return languageOptions ? <div key={'language-menu'}>
        <Dropdown menu={{
            selectable: true,
            selectedKeys: [form.state.language],
            onClick: ({key}) => {
                form.updateLanguage(key)
            },
            items: Object.entries(languageOptions).map(([key, item]) => Object.assign({key}, item))
        }}>
            <Button shape="circle"
                    icon={languageOptions[form.state.language].icon}/>
        </Dropdown>
    </div> : null
}
export default LanguageNav;