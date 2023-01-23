import {List} from 'antd';

const Item = ({children, render, ...props}) => (
    <List.Item {...props}>
        {children}
    </List.Item>);
export default Item;