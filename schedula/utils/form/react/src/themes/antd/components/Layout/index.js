import {Layout as BaseLayout} from 'antd';

const Layout = ({children, render, ...props}) => (
    <BaseLayout {...props}>
        {children}
    </BaseLayout>);
export default Layout;