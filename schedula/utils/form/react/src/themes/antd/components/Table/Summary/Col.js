import {Table} from 'antd';

const {Col: BaseCol} = Table.Summary,
    Col = ({children, render, ...props}) => (
        <BaseCol {...props}>
            {children}
        </BaseCol>);
export default Col;