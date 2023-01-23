import {List} from 'antd';

const Meta = ({children, render, ...props}) => (
    <List.Item.Meta {...props}>
        {children}
    </List.Item.Meta>);
export default Meta;