import {Popover as BasePopover} from 'antd';

const Popover = ({children, render, ...props}) => (
    <BasePopover {...props}>
        {children}
    </BasePopover>);
export default Popover;