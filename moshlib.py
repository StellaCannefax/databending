#!/usr/bin/env python
import requests as req
from PIL import Image
from subprocess import call
from random import randint, choice, shuffle
from os.path import isfile
from binascii import a2b_hex
from collections import namedtuple
import os, sys, string, argparse, json

def file_length(infile):
    return len(open(infile).readlines())

def save_file_url(url):
    if url.match("http?://"):
        response = req.get(url)
        if response.status_code == 200 or 304:
            open(filename, 'wb').write(response.content)
            print "\nfetched image file: %s" % filename
            return filename
        else:
            print "Bad response (%s) from server for this URL" % response.status_code
    else:
        print "doesn't seem to be either a local file or a url..."
        return 

def handle_options():
    defaults = json.loads(open("config.json").read())['defaults']
    parser = argparse.ArgumentParser()

    parser.add_argument("input_file")
    parser.add_argument("-f", "--frames", default=defaults['animation_frames'],
        type=int, help="Number of frames for the animation")
    parser.add_argument("-d", "--delay", default=defaults['animation_delay'],
        type=int, help="animation delay in 100ths of a second")
    parser.add_argument("-a", "--amount", default=defaults['glitch_amount'],
        type=int, help="Amount of glitch locations per frame")
    parser.add_argument("-w", "--width", default=defaults['width'],
        type=int, help="lines per glitch location")
    parser.add_argument("-s", "--saturation", default=defaults['saturation'],
        type=int, help="Saturation change (100 is unchanged)")
    parser.add_argument("-c", "--colors", default=defaults['colors'],
        type=int, help="Number of colors in the color pallete of the final GIF")
    parser.add_argument("-r", "--rotate", default=defaults['rotation_chance'], 
        type=int, help="Chance of image rotation")
    parser.add_argument("-i", "--interactive", default=False, 
        type=int, help="Turn on prompt-based interface")

    opts = parser.parse_args()

    if not isfile(opts.input_file):                           # if we don't find it,
        opts.input_file = save_file_url(opts.input_file)      # assume it's a URL
    
    return opts
    

def convertbmp(infile, outfile):
    outfile = outfile.split('.')[0] + '.bmp'
    image = Image.open(infile)
    try:
        image.save(outfile, 'BMP')
        return outfile
    except IOError:
        return ("Cannot process", infile)

def is_bmp(filename):
    if open(filename, "rb").read(2) == "BM":    
        return True
    else:
        return False


class Gifscythe():                                 # methods using Gifsicle
    
    def finalize(self, input_gif):
        print 'Optimizing and dithering final GIF...'
        call('gifsicle -O3 --colors %i --dither --batch %s' % (opts.colors, input_gif), shell=True)

class ImageMage():                                 # handles ImageMagick-based glitches
   
    # randomize saturation and hue with a range 
    def color_jitter(self, filename, hue_range):
        frame_saturation = opts.saturation + randint(-15,35)
        hue = randint(100-hue_range, 100+hue_range)
        IM_command = "mogrify -quiet -modulate 100,%i,%i %s" % (frame_saturation, hue, filename)
        call(IM_command, shell=True)

    # randomize brightness to create flashing effect, accents lines nicely
    def flashing_lights(self, filename, light_range):
        light = randint(110-light_range/2, 110+light_range)
        IM_command = "mogrify -quiet -modulate %i,100,100 %s" % (light, filename)
        call(IM_command, shell=True)
    
    # should be used BEFORE text-based glitches if you want non-horizontal glitches
    def random_rotate(self, filename, chance):
        if chance > 100: 
            chance = 100
        elif chance <= 0:
            return
        if randint(1,100) <= chance:
            IM_command = "mogrify -quiet -transpose %s" % filename
            call(IM_command, shell=True)
            return True
        else:
            return False

    # realign images rotated with the above function        
    def unrotate(self, filename):
        IM_command = "mogrify -quiet -rotate 270 %s" % filename
        call(IM_command, shell=True)
            
            
class Editor():
    
    # these list comprehensions generate arrays of random string data, run it to see
    def __init__(self):
        self.regex_targets = [a2b_hex(''.join(choice(string.hexdigits) 
                                for n in range(0,4,2))) for n in range (0,20)]
        self.regex_payloads = [a2b_hex(''.join(choice(string.hexdigits) 
                                for i in range(0, choice(range(0,24,2))))) for n in range(24)]

    def split_header(self, lines):
        if len(lines[0]) < 100:
            return lines
        else:
            lines[0] = lines[0][:100] + "\n"
            lines.insert(1, line[100:])
        return lines

    # move random pieces of specified width around in the image
    def shuffle_chunks(self, filename, amount, width, frame=1):
        lines = self.split_header(open(filename, "rb").readlines())
        targets = [randint(2, len(lines)) for n in range(amount)]                
        chunks = [{"start": n, "data": lines[n:n+width]} for n in targets]
        shuffle(targets)
        shuffle(chunks)

        for chunk in chunks:
            chunk["start"] = targets.pop()
            chunk["indexes"] = [n for n in range(chunk["start"], width) if n < len(lines)]
            for (i, value) in enumerate(chunk["indexes"]):
                if i < len(chunk["data"]):
                    lines[value] = chunk["data"][i]
                
        open("shuffled-%i-" % frame + filename, "wb").write(''.join(lines))    

    # line_processor must be a function that accepts and returns a line in the right encoding   
    def random_line_processor(self, filename, amount, width, line_processor, frame_num=1):
        buffer_lines = self.split_header(open(filename, "rb").readlines())
        targets = [randint(2, len(buffer_lines)) for n in range(amount)]

        for index in targets:
            for line in range(index, index + width):
                if line < len(buffer_lines):
                    buffer_lines[line] = line_processor(buffer_lines[line])
            
        open("glitched-%i-" % frame_num + filename, "wb").write(''.join(buffer_lines))    

    def write_junk_line(self, buffer_line):
        return choice(self.regex_payloads) + buffer_line

    def write_blank_line(self, _):
        return "\n"

    def replace_regex(self, buffer_line):
        for target in self.regex_targets:
            buffer_line = buffer_line.replace(target, choice(self.regex_payloads))
        return buffer_line                

    def replace_junk(self, filename, amount, width, frame=1):
        self.random_line_processor(filename, amount, width, self.replace_regex, frame_num=frame)

    def insert_junk(self, filename, amount, width, frame=1):
        self.random_line_processor(filename, amount, width, self.write_junk_line, frame_num=frame)

    def delete_junk(self, filename, amount, width, frame=1):
        self.random_line_processor(filename, amount, width, self.write_blank_line, frame_num=frame)


# DEPRECATED, DON'T USE IT (though it does have a certain look to it)
class SedSorceror():                               # handles sed-based effects

    def __init__(self, image):
        self.filelength = file_length(image)

    def rgb_wiggle(self, filename, outfile, cutcount):
        targets = [''.join(choice(string.hexdigits) for n in range(0,2)) for n in range (0,30)]
        for i in range(cutcount):
            target = choice(targets)
            start = randint(2, int(self.filelength * 0.90))

            if randint(0,100) > 66:
                end = "$" # end of file
            else:
                end = str(randint(start + 1, self.filelength))

            payload = ''.join(choice(string.hexdigits) for i in range(randint(0,12)))
            
            if i == 0:
                sedcommand = "sed '%i,%s s/%s/%s/g' %s > %s" % (start, end, target, payload, filename, outfile)
            else:
                sedcommand = "sed -i '%i,%s s/%s/%s/g' %s" % (start, end, target, payload, filename)
            
            print "On lines %s through line %s, '%s' will be replaced with '%s'" % (start, end, target, payload)
            call(sedcommand, shell=True)
            filename = outfile

def glitchbmp_old(infile, outfile, amount):
    outfile = outfile.split('.')[0] + '.bmp'

    sed = SedSorceror(infile)
    mage = ImageMage()
    
    rotated = mage.random_rotate(infile, opts.rotate)
    sed.rgb_wiggle(infile, outfile, amount)
    if rotated:
        print "File was rotated, trying to unrotate %s ..." % outfile
        mage.unrotate(outfile)
        mage.unrotate(infile)

    mage.color_jitter(outfile, randint(10,30))
    mage.flashing_lights(outfile, randint(10,40))

    return outfile

def glitchbmp(infile, outfile, amount):
    outfile = outfile.split('.')[0] + '.bmp'
    ed = Editor()
    mage = ImageMage()
    
    rotated = mage.random_rotate(infile, opts.rotate)
    print infile
    ed.replace_junk(infile, amount, choice(range(2,12)))
    if rotated:
        print "File was rotated, trying to unrotate %s ..." % outfile
        mage.unrotate(outfile)
        mage.unrotate(infile)

    mage.color_jitter(outfile, randint(10,30))
    mage.flashing_lights(outfile, randint(10,30))

    return outfile

def animateglitch(infile, frames, anim_delay, glitch_amount):

    convertedimage = convertbmp(infile, 'converted-%s' % infile)
    print "%s converted to %s \n" % (infile, convertedimage)
    
    i = 1
    while i <= frames:
        glitchedimage = glitchbmp(convertedimage, 'glitched-' + infile.split('.')[0] + str(i) + '.bmp', glitch_amount)
        print "%s glitched to %s \n" % (convertedimage, glitchedimage)
        print "----------------------------------------"
        i += 1

    gif = Gifscythe()
    print "\nAnimating GIF... (this may take a while)"
    filename_base = infile.split('.')[0]
    animatecommand = "convert -delay %i -loop 0 -quiet glitched*bmp %s-animated.gif" % (anim_delay, filename_base)
    call(animatecommand, shell=True)
    gif.finalize("%s-animated.gif" % filename_base)
    
    print "Done! Cleaning up...."
    call("rm glitch*.bmp convert*.bmp", shell=True)


