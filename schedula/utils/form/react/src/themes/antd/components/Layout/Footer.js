import {Layout} from 'antd';

const {Footer: BaseFooter} = Layout,
    Footer = ({children, render, ...props}) => (
        <BaseFooter {...props}>
            {children}
        </BaseFooter>);
export default Footer;