import {Spin as BaseSpin} from 'antd';

const Spin = ({children, render, ...props}) => (
    <BaseSpin {...props}>
        {children}
    </BaseSpin>);
export default Spin;