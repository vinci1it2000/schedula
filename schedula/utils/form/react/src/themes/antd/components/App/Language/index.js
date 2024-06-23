import React from 'react';
import {Button, Dropdown} from 'antd';
import './Language.css'

const LanguageNav = ({form, languages}) => {
    return <div key={'language-menu'}>
        <Dropdown menu={{
            selectable: true,
            selectedKeys: [form.state.language],
            onClick: ({key}) => {
                form.updateLanguage(key)
            },
            items: Object.entries(languages).map(([key, item]) => Object.assign({key}, item))
        }}>
            <Button shape="circle" icon={languages[form.state.language].icon}/>
        </Dropdown>
    </div>
}
export default LanguageNav;