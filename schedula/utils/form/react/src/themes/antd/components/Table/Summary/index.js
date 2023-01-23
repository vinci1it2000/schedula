import {Table} from 'antd';

const {Summary: BaseSummary} = Table,
    Summary = ({children, render, ...props}) => (
        <BaseSummary {...props}>
            {children}
        </BaseSummary>);
export default Summary;