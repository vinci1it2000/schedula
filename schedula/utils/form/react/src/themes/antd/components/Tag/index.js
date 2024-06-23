import {Tag as BaseTag} from 'antd';

const Tag = ({children, render, ...props}) => (
    <BaseTag {...props}>
        {children}
    </BaseTag>);
export default Tag;