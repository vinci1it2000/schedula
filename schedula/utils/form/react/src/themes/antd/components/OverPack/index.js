import {OverPack as BaseOverPack} from 'rc-scroll-anim';

const OverPack = ({children, render, ...props}) => (
    <BaseOverPack {...props}>
        {children}
    </BaseOverPack>);
export default OverPack;