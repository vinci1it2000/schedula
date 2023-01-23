import {Segmented as BaseSegmented} from 'antd';

const Segmented = ({children, render, ...props}) => (
    <BaseSegmented {...props}>
        {children}
    </BaseSegmented>);
export default Segmented;