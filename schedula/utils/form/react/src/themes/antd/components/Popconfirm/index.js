import {Popconfirm as BasePopconfirm} from 'antd';

const Popconfirm = ({children, render, ...props}) => (
    <BasePopconfirm {...props}>
        {children}
    </BasePopconfirm>);
export default Popconfirm;