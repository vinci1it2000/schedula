import {useLocaleStore} from "../../../models/locale";
import React, {useEffect} from 'react';
import {Dropdown} from 'antd';

const LanguageNav = ({form, languages}) => {
    const {changeLocale, locale} = useLocaleStore()
    const language = form.state.language
    useEffect(() => {
        if (locale.language !== language)
            changeLocale(form, language)
    }, [language])
    return <Dropdown
        key={'language-menu'}
        menu={{
            selectedKeys: [form.state.language],
            onClick: ({key}) => {
                form.updateLanguage(key, () => {
                    changeLocale(form, key)
                })
            },
            items: Object.entries(languages).map(([key, item]) => Object.assign({key}, item))
        }}>
        <div>{languages[form.state.language].icon}</div>
    </Dropdown>
}
export default LanguageNav;