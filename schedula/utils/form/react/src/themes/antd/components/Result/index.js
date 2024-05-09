import {Result as BaseResult} from 'antd';

const Result = ({children, render, ...props}) => (
    <BaseResult {...props}>
        {children}
    </BaseResult>);
export default Result;