import {Tabs as BaseTabs} from 'antd';
import './Tabs.css'

const Tabs = ({children, render, items, ...props}) => {
    const _items = items.map((item, index) => (
        {...item, key: index, children: children[index]}
    ))
    return <BaseTabs
        type="card" size="small" items={_items} destroyInactiveTabPane={true}
        tabBarGutter={2}
        {...props}
    />
};
export default Tabs;