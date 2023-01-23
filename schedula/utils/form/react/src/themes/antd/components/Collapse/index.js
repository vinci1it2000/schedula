import {Collapse as BaseCollapse} from 'antd';

const Collapse = ({children, render, ...props}) => (
    <BaseCollapse {...props}>
        {children}
    </BaseCollapse>);
export default Collapse;