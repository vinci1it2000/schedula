import {Alert as BaseAlert} from 'antd';

const Alert = ({children, render, ...props}) => (
    <BaseAlert {...props}>
        {children}
    </BaseAlert>);
export default Alert;