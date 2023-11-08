import {useLocaleStore} from "../../../models/locale";
import React, {useEffect} from 'react';
import {Dropdown} from 'antd';

const LanguageNav = ({form, languages}) => {
    const {changeLocale, locale} = useLocaleStore()
    useEffect(() => {
        if (locale.language !== form.state.language)
            changeLocale(form.state.language)
    })
    return <Dropdown
        key={'language-menu'}
        menu={{
            selectedKeys: [form.state.language],
            onClick: ({key}) => {
                form.updateLanguage(key)
                changeLocale(key)
            },
            items: languages
        }}>
        <div>{languages.filter(({key}) => key === form.state.language)[0].icon}</div>
    </Dropdown>
}
export default LanguageNav;