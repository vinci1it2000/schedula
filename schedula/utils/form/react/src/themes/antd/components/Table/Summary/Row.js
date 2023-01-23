import {Table} from 'antd';

const {Row: BaseRow} = Table.Summary,
    Row = ({children, render, ...props}) => (
        <BaseRow {...props}>
            {children}
        </BaseRow>);
export default Row;