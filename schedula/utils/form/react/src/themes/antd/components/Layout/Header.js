import {Layout} from 'antd';

const {Header: BaseHeader} = Layout,
    Header = ({children, render, ...props}) => (
        <BaseHeader {...props}>
            {children}
        </BaseHeader>);
export default Header;