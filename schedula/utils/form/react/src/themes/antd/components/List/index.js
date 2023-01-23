import {List as BaseList} from 'antd';

const List = ({children, render, ...props}) => (
    <BaseList {...props}>
        {children}
    </BaseList>);
export default List;