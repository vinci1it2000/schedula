import {Tooltip as BaseTooltip} from 'antd';

const Tooltip = ({children, render, ...props}) => (
    <BaseTooltip {...props}>
        {children}
    </BaseTooltip>);
export default Tooltip;