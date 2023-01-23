import {Carousel as BaseCarousel} from 'antd';

const Carousel = ({children, render, ...props}) => (
    <BaseCarousel autoplay={true} {...props}>
        {children}
    </BaseCarousel>
);
export default Carousel;