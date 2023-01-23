import {Table as BaseTable} from 'antd';

const Table = ({children, render, ...props}) => (
    <BaseTable {...props}>
        {children}
    </BaseTable>);
export default Table;