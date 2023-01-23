import {Col as BaseCol} from 'antd';

const Col = ({children, render, ...props}) => (
    <BaseCol {...props}>
        {children}
    </BaseCol>);
export default Col;